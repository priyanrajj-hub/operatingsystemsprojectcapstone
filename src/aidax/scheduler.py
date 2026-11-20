"""
AI-DAX Lite: Contextual Bandit CPU Scheduler (LinUCB)
=====================================================
Adaptive CPU scheduling simulator using a LinUCB contextual bandit
that learns from measured outcomes (actual CPU/context-switch deltas).

Features:
- Cold-start heuristic fallback (~first 20 decisions per process).
- Online LinUCB multi-armed bandit targeting P-cores (Action 0) and E-cores (Action 1).
- Measured reward: R_t = -(alpha * norm_involuntary_ctx + beta * energy_proxy).
- PID-reuse guard via psutil Process create_time() cross-verification.
- Atomic CSV and JSON state persistence via tempfile + os.replace.
- Non-root user-space CPU affinity management with graceful cleanup.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import psutil

from core.fs import atomic_write_json, atomic_write_text

warnings.filterwarnings("ignore")

logger = logging.getLogger("aidax.scheduler")

CSV_HEADER = (
    "timestamp,pid,true_type,action,assigned_cores,decision_source,"
    "cpu_percent,vol_ctx_rate,invol_ctx_rate,time_since_switch,"
    "current_core_assignment,reward,cumulative_regret,confidence_ucb,"
    "alpha_param,beta_param\n"
)


@dataclass
class SchedulerConfig:
    """Configuration parameters for the LinUCB scheduler."""

    alpha_reward: float = 0.7
    beta_reward: float = 0.3
    exploration: float = 1.5
    cold_start_threshold: int = 20
    p_core_energy_cost: float = 1.0
    e_core_energy_cost: float = 0.3
    invol_ctx_norm_divisor: float = 1000.0
    pid_file: str = "pids.txt"
    log_file: str = "scheduler_log.csv"
    stats_file: str = "bandit_stats.json"
    cycle_interval_s: float = 1.0


class LinUCBArm:
    """
    One arm of the LinUCB contextual bandit.

    Maintains:
      A     — (d x d) design matrix (regularised with ridge lambda * I)
      b     — (d,) reward-weighted context accumulator
      A_inv — exact inverse maintained incrementally via Sherman-Morrison rank-1 updates
      theta — A^{-1} b parameter vector
    """

    def __init__(self, d: int, exploration_alpha: float = 1.5, ridge_lambda: float = 1.0) -> None:
        self.d = d
        self.exploration_alpha = exploration_alpha
        self.ridge_lambda = ridge_lambda
        self.A = ridge_lambda * np.eye(d, dtype=float)
        self.b = np.zeros(d, dtype=float)
        self.A_inv = (1.0 / ridge_lambda) * np.eye(d, dtype=float)
        self.theta = np.zeros(d, dtype=float)

    def get_ucb_score(self, x: np.ndarray) -> float:
        """Return UCB score = expected reward + exploration bonus."""
        expected = float(x @ self.theta)
        var = float(x @ self.A_inv @ x)
        uncertainty = float(np.sqrt(np.maximum(0.0, var)))
        return expected + self.exploration_alpha * uncertainty

    def _recompute(self) -> None:
        """Maintained for backward compatibility; state is updated incrementally via Sherman-Morrison."""
        pass

    def update(self, x: np.ndarray, reward: float) -> None:
        """Incremental Sherman-Morrison rank-1 update with numerical guards."""
        if not np.all(np.isfinite(x)) or not np.isfinite(reward):
            return

        u = self.A_inv @ x
        denom = 1.0 + float(x @ u)
        if denom > 1e-12:
            self.A_inv -= np.outer(u, u) / denom
        else:
            self.A_inv = np.linalg.inv(self.A + np.outer(x, x))

        self.A += np.outer(x, x)
        self.b += reward * x
        self.theta = self.A_inv @ self.b


class LinUCBBandit:
    """
    Two-armed LinUCB contextual bandit for CPU core allocation.

    Action 0 = route to Performance (P) cores.
    Action 1 = route to Efficient (E) cores.
    """

    def __init__(self, context_dim: int, exploration_alpha: float = 1.5) -> None:
        self.context_dim = context_dim
        self.arms = [
            LinUCBArm(context_dim, exploration_alpha),
            LinUCBArm(context_dim, exploration_alpha),
        ]
        self.total_decisions = 0

    def select_action(self, context: np.ndarray) -> tuple[int, float]:
        """Return (action_idx, ucb_score) for the best arm given context."""
        scores = [arm.get_ucb_score(context) for arm in self.arms]
        action = int(np.argmax(scores))
        return action, scores[action]

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        """Update selected arm parameters with observed reward."""
        self.arms[action].update(context, reward)
        self.total_decisions += 1

    def get_params_snapshot(self) -> dict[str, Any]:
        """Return serialisable snapshot of bandit internals for the dashboard."""
        for arm in self.arms:
            arm._recompute()
        return {
            "total_decisions": self.total_decisions,
            "arm_0_theta": self.arms[0].theta.tolist(),
            "arm_1_theta": self.arms[1].theta.tolist(),
        }


class OnlineScaler:
    """
    Welford's online algorithm for incremental mean and variance normalisation.
    """

    def __init__(self, d: int) -> None:
        self.d = d
        self.n = 0
        self.mean = np.zeros(d, dtype=float)
        self.M2 = np.zeros(d, dtype=float)

    def update(self, x: np.ndarray) -> None:
        """Incorporate observation x into running mean and variance."""
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    def transform(self, x: np.ndarray) -> np.ndarray:
        """Standardize feature vector x; passes raw features through when n < 2."""
        if self.n < 2:
            return x.copy()
        var = self.M2 / (self.n - 1)
        std = np.sqrt(np.maximum(var, 1e-8))
        return (x - self.mean) / std


class AIScheduler:
    """
    Contextual bandit CPU affinity scheduler.
    """

    CONTEXT_DIM = 5

    def __init__(
        self,
        config: SchedulerConfig | None = None,
        alpha_reward: float | None = None,
        beta_reward: float | None = None,
        exploration: float | None = None,
        cold_start_threshold: int | None = None,
        pid_file: str | None = None,
        log_file: str | None = None,
        stats_file: str | None = None,
    ) -> None:
        if config is None:
            self.config = SchedulerConfig()
        else:
            self.config = config

        if alpha_reward is not None:
            self.config.alpha_reward = alpha_reward
        if beta_reward is not None:
            self.config.beta_reward = beta_reward
        if exploration is not None:
            self.config.exploration = exploration
        if cold_start_threshold is not None:
            self.config.cold_start_threshold = cold_start_threshold
        if pid_file is not None:
            self.config.pid_file = pid_file
        if log_file is not None:
            self.config.log_file = log_file
        if stats_file is not None:
            self.config.stats_file = stats_file

        self.p_cores, self.e_cores = self.detect_cores()
        self.history: dict[int, dict[str, Any]] = {}
        self.pending: dict[int, tuple[int, np.ndarray]] = {}

        self.bandit = LinUCBBandit(self.CONTEXT_DIM, exploration_alpha=self.config.exploration)
        self.scaler = OnlineScaler(self.CONTEXT_DIM)

        self.alpha_reward = self.config.alpha_reward
        self.beta_reward = self.config.beta_reward
        self.cold_start_threshold = self.config.cold_start_threshold

        self.pid_decision_count: dict[int, int] = {}
        self.cumulative_regret = 0.0
        self.best_fixed_rewards: dict[int, float] = {0: 0.0, 1: 0.0}
        self.total_reward = 0.0

        self.stats_file = self.config.stats_file
        self.log_file = self.config.log_file
        self.pid_file = self.config.pid_file

        self.heuristic_count = 0
        self.bandit_count = 0

    def detect_cores(self) -> tuple[list[int], list[int]]:
        """
        Detect P-cores and E-cores using normalized hardware topology detection.
        Labels unverified platforms as 'SIMULATED PARTITION'.
        """
        try:
            from hardware.detection import detect_cpu_topology

            topo = detect_cpu_topology()
            if topo.p_cores and topo.e_cores:
                if not topo.is_heterogeneous:
                    logger.warning(
                        "SIMULATED PARTITION: Host CPU does not exhibit verified heterogeneous hardware topology. "
                        "Scheduler operating in simulated P/E partition mode."
                    )
                return list(topo.p_cores), list(topo.e_cores)
        except Exception as e:
            logger.debug("Hardware topology module fallback in aidax.scheduler: %s", e)

        total = os.cpu_count() or 4
        half = max(1, total // 2)
        logger.warning(
            "SIMULATED PARTITION: Hardware topology undetectable. Splitting %d logical cores 50/50.",
            total,
        )
        return list(range(half)), list(range(half, total))

    def get_active_pids(self) -> list[tuple[int, str]]:
        """
        Read target PIDs from PID file with creation-time verification
        to prevent operating system PID-reuse attacks or misattributions.
        """
        active: list[tuple[int, str]] = []
        if not os.path.exists(self.pid_file):
            return active

        current_username: str | None = None
        try:
            current_username = psutil.Process().username()
        except Exception:
            pass

        try:
            with open(self.pid_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        pid = data["pid"]
                        start_time = data["start_time"]
                        p = psutil.Process(pid)
                        if p.create_time() == start_time:
                            if current_username is None or p.username() == current_username:
                                active.append((pid, data.get("type", "Unknown")))
                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        json.JSONDecodeError,
                        KeyError,
                    ):
                        continue
        except FileNotFoundError:
            pass
        return active

    def _compute_reward(self, action: int, invol_ctx_rate: float) -> float:
        """
        Compute scalar bandit reward:
        Reward = -(alpha * norm_involuntary_ctx + beta * energy_proxy)
        """
        energy_proxy = (
            self.config.p_core_energy_cost if action == 0 else self.config.e_core_energy_cost
        )
        norm_invol = min(invol_ctx_rate / self.config.invol_ctx_norm_divisor, 1.0)
        return -(self.alpha_reward * norm_invol + self.beta_reward * energy_proxy)

    def _get_current_core_assignment(self, pid: int) -> float:
        """Return 0.0 if affinity overlaps mostly P-cores, 1.0 if mostly E-cores."""
        try:
            p = psutil.Process(pid)
            affinity = p.cpu_affinity()
            if not affinity:
                return 0.5
            p_overlap = len(set(affinity) & set(self.p_cores))
            e_overlap = len(set(affinity) & set(self.e_cores))
            if p_overlap >= e_overlap:
                return 0.0
            return 1.0
        except Exception:
            return 0.5

    def _write_bandit_stats(self) -> None:
        """Atomically persist bandit parameters and regret metrics to JSON."""
        stats = {
            "total_decisions": self.bandit.total_decisions,
            "heuristic_count": self.heuristic_count,
            "bandit_count": self.bandit_count,
            "cumulative_regret": round(self.cumulative_regret, 4),
            "alpha_reward": self.alpha_reward,
            "beta_reward": self.beta_reward,
            "arm_params": self.bandit.get_params_snapshot(),
        }
        try:
            atomic_write_json(self.stats_file, stats)
        except Exception as e:
            logger.debug("Failed atomic write for bandit stats: %s", e)

    def _write_csv_rows(self, rows: list[str]) -> None:
        """Atomically append rows to the CSV log, keeping the most recent entries."""
        if not rows:
            return

        target = self.log_file
        log_lines: list[str] = []

        if os.path.exists(target):
            try:
                with open(target, encoding="utf-8") as f:
                    log_lines = f.readlines()[-300:]
            except Exception:
                log_lines = []

        log_lines.extend(rows)
        content_parts: list[str] = []
        if not log_lines or not log_lines[0].startswith("timestamp"):
            content_parts.append(CSV_HEADER)
        for line in log_lines:
            if line.startswith("timestamp"):
                continue
            content_parts.append(line)

        try:
            atomic_write_text(target, "".join(content_parts))
        except Exception as e:
            logger.debug("Failed atomic CSV write: %s", e)

    def run_cycle(self) -> list[str]:
        """Execute one scheduling and adaptation cycle across all active processes."""
        cycle_start = time.time()
        active = self.get_active_pids()
        rows: list[str] = []

        for pid, true_type in active:
            try:
                p = psutil.Process(pid)
                cpu = p.cpu_percent(interval=0.0)
                ctx = p.num_ctx_switches()

                # Prime metrics on first cycle
                if pid not in self.history:
                    p.cpu_percent(interval=None)
                    self.history[pid] = {
                        "vol": ctx.voluntary,
                        "invol": ctx.involuntary,
                        "time": cycle_start,
                        "last_switch_time": cycle_start,
                    }
                    self.pid_decision_count[pid] = 0
                    continue

                dt = cycle_start - self.history[pid]["time"]
                if dt <= 0:
                    continue

                vol_rate = (ctx.voluntary - self.history[pid]["vol"]) / dt
                invol_rate = (ctx.involuntary - self.history[pid]["invol"]) / dt
                time_since_switch = cycle_start - self.history[pid]["last_switch_time"]
                current_core = self._get_current_core_assignment(pid)

                self.history[pid]["vol"] = ctx.voluntary
                self.history[pid]["invol"] = ctx.involuntary
                self.history[pid]["time"] = cycle_start

                raw_context = np.array(
                    [cpu, vol_rate, invol_rate, time_since_switch, current_core],
                    dtype=float,
                )
                self.scaler.update(raw_context)
                context = self.scaler.transform(raw_context)

                # Process pending reward from previous cycle
                reward_value = 0.0
                if pid in self.pending:
                    prev_action, prev_context = self.pending[pid]
                    reward_value = self._compute_reward(prev_action, invol_rate)
                    self.bandit.update(prev_action, prev_context, reward_value)
                    self.total_reward += reward_value

                    for a in [0, 1]:
                        r_a = self._compute_reward(a, invol_rate)
                        self.best_fixed_rewards[a] += r_a
                    best_possible = max(self.best_fixed_rewards[0], self.best_fixed_rewards[1])
                    self.cumulative_regret = best_possible - self.total_reward

                self.pid_decision_count[pid] = self.pid_decision_count.get(pid, 0) + 1

                # Dynamic cold start: heuristic during system warmup or during per-PID 2-cycle priming
                is_cold = (self.bandit.total_decisions < self.cold_start_threshold) or (
                    self.pid_decision_count[pid] < 2
                )

                if is_cold:
                    heur_class = "Heavy" if (cpu > 20 and vol_rate < 500) else "Light"
                    action = 0 if heur_class == "Heavy" else 1
                    decision_source = "heuristic"
                    ucb_score = 0.0
                    self.heuristic_count += 1
                else:
                    action, ucb_score = self.bandit.select_action(context)
                    decision_source = "bandit"
                    self.bandit_count += 1

                self.pending[pid] = (action, context)

                action_label = "P-core" if action == 0 else "E-core"
                target_cores = self.p_cores if action == 0 else self.e_cores
                try:
                    p.cpu_affinity(target_cores)
                    self.history[pid]["last_switch_time"] = cycle_start
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    pass

                rows.append(
                    f"{cycle_start},{pid},{true_type},{action_label},"
                    f'"{target_cores}",{decision_source},{cpu:.1f},'
                    f"{vol_rate:.1f},{invol_rate:.1f},{time_since_switch:.1f},"
                    f"{current_core:.1f},{reward_value:.4f},"
                    f"{self.cumulative_regret:.4f},{ucb_score:.4f},"
                    f"{self.alpha_reward},{self.beta_reward}\n"
                )

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                logger.error("Error for PID %d: %s", pid, e)

        self._write_csv_rows(rows)
        self._write_bandit_stats()
        # Evict dead processes to prevent memory leak
        self.prune_dead_pids({pid for pid, _ in active})
        return rows

    def prune_dead_pids(self, active_pids: set[int]) -> None:
        """Evict cached state for dead processes to prevent memory leaks."""
        known = (
            set(self.history.keys())
            | set(self.pid_decision_count.keys())
            | set(self.pending.keys())
        )
        dead = known - active_pids
        for pid in dead:
            self.history.pop(pid, None)
            self.pid_decision_count.pop(pid, None)
            self.pending.pop(pid, None)

    def reset_affinities(self) -> int:
        """Reset CPU affinities of all active tracked processes to all available cores."""
        logger.info("Resetting process CPU affinities...")
        active = self.get_active_pids()
        total_cores = os.cpu_count() or 4
        all_cores = list(range(total_cores))
        count = 0
        for pid, _ in active:
            try:
                p = psutil.Process(pid)
                if hasattr(p, "cpu_affinity"):
                    p.cpu_affinity(all_cores)
                    count += 1
            except Exception:
                pass
        return count

    def run(self) -> None:
        """Continuous execution loop."""
        logger.info(
            "Starting LinUCB Bandit Scheduler (alpha=%.2f, beta=%.2f, cold_start=%d)",
            self.alpha_reward,
            self.beta_reward,
            self.cold_start_threshold,
        )
        logger.info("P-cores: %s, E-cores: %s", self.p_cores, self.e_cores)

        while True:
            self.run_cycle()
            time.sleep(self.config.cycle_interval_s)


def main() -> None:
    """CLI entry point for aidax-scheduler."""
    parser = argparse.ArgumentParser(description="AI-DAX Lite: LinUCB Bandit CPU Scheduler")
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.7,
        help="Reward weight for involuntary context switches (default: 0.7)",
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=0.3,
        help="Reward weight for energy proxy cost (default: 0.3)",
    )
    parser.add_argument(
        "--exploration",
        type=float,
        default=1.5,
        help="LinUCB exploration parameter (default: 1.5)",
    )
    parser.add_argument(
        "--cold-start",
        type=int,
        default=20,
        help="Heuristic-only decisions per PID before bandit takes over (default: 20)",
    )
    parser.add_argument(
        "--pid-file",
        type=str,
        default="pids.txt",
        help="Path to process tracking file (default: pids.txt)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="scheduler_log.csv",
        help="Path to decision CSV log (default: scheduler_log.csv)",
    )
    parser.add_argument(
        "--stats-file",
        type=str,
        default="bandit_stats.json",
        help="Path to bandit JSON stats (default: bandit_stats.json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Emergency recovery: release all tracked processes from affinity constraints and exit",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    )

    config = SchedulerConfig(
        alpha_reward=args.alpha,
        beta_reward=args.beta,
        exploration=args.exploration,
        cold_start_threshold=args.cold_start,
        pid_file=args.pid_file,
        log_file=args.log_file,
        stats_file=args.stats_file,
    )
    scheduler = AIScheduler(config=config)

    if args.recover:
        logger.info("Executing affinity recovery across all tracked processes...")
        released = scheduler.reset_affinities()
        logger.info("Affinity recovery complete: %d processes restored to all cores.", released)
        sys.exit(0)

    import atexit

    atexit.register(scheduler.reset_affinities)

    def shutdown_handler(signum: int, frame: Any) -> None:
        logger.info("Signal %d received. Resetting affinities and exiting...", signum)
        scheduler.reset_affinities()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown_handler)

    scheduler.run()


# Standard alias
CPUScheduler = AIScheduler

if __name__ == "__main__":
    main()
