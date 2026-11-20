"""
AI-DAX Lite: Contextual Bandit CPU Scheduler (LinUCB)
=====================================================
Replaces the previous RandomForest classifier with a LinUCB contextual bandit
that learns from MEASURED outcomes (actual CPU/context-switch deltas), not
from heuristic-generated proxy labels.

Key research contribution:
- The heuristic is ONLY a cold-start fallback (first ~20 decisions per PID).
- After cold-start, the LinUCB bandit selects actions based on Upper Confidence
  Bound exploration/exploitation, updating its parameters with REAL measured
  rewards after each decision cycle.
- Reward: R_t = -(alpha * norm_involuntary_ctx + beta * energy_proxy)
  where energy_proxy = 1.0 for P-core, 0.3 for E-core (standard assumption
  when direct wattage metering is unavailable — P-cores draw ~3x the power
  of E-cores on Intel hybrid architectures).

All existing safety mechanisms are preserved:
- PID-reuse guard via create_time() cross-check
- Atomic CSV writes via tempfile + os.replace
- Graceful affinity reset on SIGINT/SIGTERM
- Non-root user-space operation via psutil
"""

import os
import sys
import time
import json
import signal
import psutil
import tempfile
import warnings
import argparse
import numpy as np

warnings.filterwarnings('ignore')

LOG_FILE = 'scheduler_log.csv'
PID_FILE = 'pids.txt'

# CSV header for the enriched bandit log
CSV_HEADER = (
    "timestamp,pid,true_type,action,assigned_cores,decision_source,"
    "cpu_percent,vol_ctx_rate,invol_ctx_rate,time_since_switch,"
    "current_core_assignment,reward,cumulative_regret,confidence_ucb,"
    "alpha_param,beta_param\n"
)

# ─────────────────────────────────────────────────────────────────────
# LinUCB Contextual Bandit
# ─────────────────────────────────────────────────────────────────────

class LinUCBArm:
    """
    One arm of the LinUCB bandit (represents one action: route_to_P or route_to_E).

    Maintains:
      A  — (d x d) design matrix (identity-initialised for regularisation)
      b  — (d,)  reward-weighted context accumulator
      theta — A^{-1} b  (parameter vector, recomputed lazily)

    UCB score for context x:
      score = x^T theta + exploration_alpha * sqrt(x^T A^{-1} x)

    Reference: Li et al., "A Contextual-Bandit Approach to Personalized News
    Article Recommendation," WWW 2010.
    """
    def __init__(self, d, exploration_alpha=1.5):
        self.d = d
        self.exploration_alpha = exploration_alpha
        self.A = np.eye(d)           # d x d identity
        self.b = np.zeros(d)         # d-vector
        self.A_inv = np.eye(d)       # cached inverse
        self.theta = np.zeros(d)     # cached parameter vector
        self._dirty = False

    def _recompute(self):
        if self._dirty:
            self.A_inv = np.linalg.inv(self.A)
            self.theta = self.A_inv @ self.b
            self._dirty = False

    def get_ucb_score(self, x):
        """Return UCB score = expected reward + exploration bonus."""
        self._recompute()
        expected = x @ self.theta
        # Exploration bonus: alpha * sqrt(x^T A^{-1} x)
        uncertainty = np.sqrt(x @ self.A_inv @ x)
        return expected + self.exploration_alpha * uncertainty

    def update(self, x, reward):
        """Online update after observing reward for context x."""
        self.A += np.outer(x, x)
        self.b += reward * x
        self._dirty = True


class LinUCBBandit:
    """
    Two-armed LinUCB contextual bandit for CPU routing.
    Action 0 = route to P-cores, Action 1 = route to E-cores.
    """
    def __init__(self, context_dim, exploration_alpha=1.5):
        self.arms = [
            LinUCBArm(context_dim, exploration_alpha),  # Action 0: P-core
            LinUCBArm(context_dim, exploration_alpha),  # Action 1: E-core
        ]
        self.total_decisions = 0

    def select_action(self, context):
        """Return (action_idx, ucb_score) for the best arm given context."""
        scores = [arm.get_ucb_score(context) for arm in self.arms]
        action = int(np.argmax(scores))
        return action, scores[action]

    def update(self, action, context, reward):
        """Update the selected arm with the measured reward."""
        self.arms[action].update(context, reward)
        self.total_decisions += 1

    def get_params_snapshot(self):
        """Return serialisable snapshot of bandit internals for the dashboard."""
        return {
            'total_decisions': self.total_decisions,
            'arm_0_theta': self.arms[0].theta.tolist(),
            'arm_1_theta': self.arms[1].theta.tolist(),
        }


# ─────────────────────────────────────────────────────────────────────
# Feature Scaling Helper
# ─────────────────────────────────────────────────────────────────────

class OnlineScaler:
    """
    Welford's online algorithm for incremental mean/variance computation.
    Normalises features to zero-mean, unit-variance without storing all data.
    """
    def __init__(self, d):
        self.n = 0
        self.mean = np.zeros(d)
        self.M2 = np.zeros(d)

    def update(self, x):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    def transform(self, x):
        if self.n < 2:
            return x  # Not enough data to normalise yet
        var = self.M2 / (self.n - 1)
        std = np.sqrt(np.maximum(var, 1e-8))
        return (x - self.mean) / std


# ─────────────────────────────────────────────────────────────────────
# AI Scheduler (Bandit Version)
# ─────────────────────────────────────────────────────────────────────

class AIScheduler:
    # Context vector: [cpu_percent, vol_ctx_rate, invol_ctx_rate,
    #                   time_since_last_switch, current_core_assignment]
    CONTEXT_DIM = 5

    def __init__(self, alpha_reward=0.7, beta_reward=0.3, exploration=1.5,
                 cold_start_threshold=20):
        self.p_cores, self.e_cores = self.detect_cores()
        self.history = {}       # pid -> last-cycle metrics
        self.pending = {}       # pid -> (action, context) awaiting next-cycle reward

        # Bandit setup
        self.bandit = LinUCBBandit(self.CONTEXT_DIM, exploration_alpha=exploration)
        self.scaler = OnlineScaler(self.CONTEXT_DIM)

        # Reward parameters (exposed for sensitivity sweep)
        self.alpha_reward = alpha_reward
        self.beta_reward = beta_reward
        self.cold_start_threshold = cold_start_threshold

        # Per-PID decision counters for cold-start graduation
        self.pid_decision_count = {}

        # Regret tracking
        self.cumulative_regret = 0.0
        self.best_fixed_rewards = {0: 0.0, 1: 0.0}  # track reward sum per action
        self.total_reward = 0.0

        # Bandit stats file for dashboard API
        self.stats_file = 'bandit_stats.json'
        self.heuristic_count = 0
        self.bandit_count = 0

    def detect_cores(self):
        """Attempts to read hardware topology. Falls back cleanly on Windows."""
        p_cores, e_cores = [], []
        try:
            import glob
            core_types = glob.glob("/sys/devices/system/cpu/cpu*/topology/core_type")
            for file in core_types:
                cpu_id = int(file.split('cpu')[1].split('/')[0])
                with open(file, 'r') as f:
                    c_type = int(f.read().strip())
                if c_type == 0: p_cores.append(cpu_id)
                elif c_type == 1: e_cores.append(cpu_id)

            if p_cores and e_cores:
                print(f"[SYSFS] Detected P-cores: {p_cores}, E-cores: {e_cores}")
                return p_cores, e_cores
        except Exception:
            pass

        # Fallback: Try frequency-based detection (Linux)
        try:
            import glob
            freqs = {}
            freq_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq")
            for file in freq_files:
                cpu_id = int(file.split('cpu')[1].split('/')[0])
                with open(file, 'r') as f:
                    freqs[cpu_id] = int(f.read().strip())

            if freqs:
                unique_freqs = sorted(list(set(freqs.values())), reverse=True)
                if len(unique_freqs) > 1:
                    threshold = (unique_freqs[0] + unique_freqs[-1]) / 2
                    p_cores = [c for c, f in freqs.items() if f > threshold]
                    e_cores = [c for c, f in freqs.items() if f <= threshold]
                    print(f"[FREQ FALLBACK] P-cores: {p_cores}, E-cores: {e_cores}")
                    return p_cores, e_cores
        except Exception:
            pass

        print("[FALLBACK] Hardware topology undetectable. Splitting adjacent cores 50/50.")
        total = os.cpu_count() or 4
        half = total // 2
        return list(range(half)), list(range(half, total))

    def get_active_pids(self):
        """Reads target PIDs safely with PID-reuse guard via create_time()."""
        active = []
        try:
            with open(PID_FILE, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        pid = data['pid']
                        start_time = data['start_time']

                        p = psutil.Process(pid)
                        # Security: only act on our own processes, verify PID not recycled
                        if (p.create_time() == start_time and
                                p.username() == psutil.Process().username()):
                            active.append((pid, data['type']))
                    except Exception:
                        continue
        except FileNotFoundError:
            pass
        return active

    def _compute_reward(self, action, invol_ctx_rate):
        """
        Reward = -(alpha * normalised_involuntary_ctx_switches + beta * energy_proxy)

        Energy proxy: P-core (action=0) draws ~3x power of E-core (action=1).
        This is a standard assumption when direct wattage metering is unavailable
        on Intel hybrid architectures (Alder Lake / Raptor Lake).
        """
        energy_proxy = 1.0 if action == 0 else 0.3
        # Clamp invol_ctx_rate to [0, 1] range for reward stability
        norm_invol = min(invol_ctx_rate / 1000.0, 1.0)  # normalise to ~1000 switches/s max
        reward = -(self.alpha_reward * norm_invol + self.beta_reward * energy_proxy)
        return reward

    def _get_current_core_assignment(self, pid):
        """Return 0.0 if mostly on P-cores, 1.0 if mostly on E-cores."""
        try:
            p = psutil.Process(pid)
            affinity = p.cpu_affinity()
            p_overlap = len(set(affinity) & set(self.p_cores))
            e_overlap = len(set(affinity) & set(self.e_cores))
            if p_overlap >= e_overlap:
                return 0.0
            return 1.0
        except Exception:
            return 0.5

    def _write_bandit_stats(self):
        """Atomically write bandit stats for the dashboard API to read."""
        stats = {
            'total_decisions': self.bandit.total_decisions,
            'heuristic_count': self.heuristic_count,
            'bandit_count': self.bandit_count,
            'cumulative_regret': round(self.cumulative_regret, 4),
            'alpha_reward': self.alpha_reward,
            'beta_reward': self.beta_reward,
            'arm_params': self.bandit.get_params_snapshot(),
        }
        try:
            dir_name = os.path.dirname(os.path.abspath(self.stats_file)) or '.'
            tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.json')
            with os.fdopen(tmp_fd, 'w') as f:
                json.dump(stats, f)
            os.replace(tmp_path, self.stats_file)
        except Exception:
            pass

    def run(self):
        print(f"[SCHEDULER] Starting LinUCB Bandit Scheduler "
              f"(alpha={self.alpha_reward}, beta={self.beta_reward}, "
              f"cold_start={self.cold_start_threshold})")
        print(f"[SCHEDULER] P-cores: {self.p_cores}, E-cores: {self.e_cores}")

        while True:
            cycle_start = time.time()
            active = self.get_active_pids()
            rows = []

            for pid, true_type in active:
                try:
                    p = psutil.Process(pid)
                    cpu = p.cpu_percent(interval=0.0)
                    ctx = p.num_ctx_switches()

                    # ── First observation: initialise baselines ──
                    if pid not in self.history:
                        p.cpu_percent(interval=None)  # prime psutil's internal counter
                        self.history[pid] = {
                            'vol': ctx.voluntary,
                            'invol': ctx.involuntary,
                            'time': cycle_start,
                            'last_switch_time': cycle_start,
                        }
                        self.pid_decision_count[pid] = 0
                        continue

                    dt = cycle_start - self.history[pid]['time']
                    if dt <= 0:
                        continue

                    vol_rate = (ctx.voluntary - self.history[pid]['vol']) / dt
                    invol_rate = (ctx.involuntary - self.history[pid]['invol']) / dt
                    time_since_switch = cycle_start - self.history[pid]['last_switch_time']
                    current_core = self._get_current_core_assignment(pid)

                    # Update history
                    self.history[pid]['vol'] = ctx.voluntary
                    self.history[pid]['invol'] = ctx.involuntary
                    self.history[pid]['time'] = cycle_start

                    # ── Build context vector ──
                    raw_context = np.array([
                        cpu, vol_rate, invol_rate, time_since_switch, current_core
                    ])
                    self.scaler.update(raw_context)
                    context = self.scaler.transform(raw_context)

                    # ── Process pending reward from PREVIOUS cycle ──
                    # This is the critical research fix: reward is measured from
                    # the ACTUAL outcome of the previous routing decision, not
                    # from the heuristic label.
                    reward_value = 0.0
                    if pid in self.pending:
                        prev_action, prev_context = self.pending[pid]
                        reward_value = self._compute_reward(prev_action, invol_rate)
                        self.bandit.update(prev_action, prev_context, reward_value)
                        self.total_reward += reward_value

                        # Regret: compare against best fixed action in hindsight
                        for a in [0, 1]:
                            r_a = self._compute_reward(a, invol_rate)
                            self.best_fixed_rewards[a] += r_a
                        best_possible = max(self.best_fixed_rewards[0],
                                            self.best_fixed_rewards[1])
                        self.cumulative_regret = best_possible - self.total_reward

                    # ── Decision: Cold-start heuristic or Bandit ──
                    t0_inf = time.time()
                    self.pid_decision_count[pid] = self.pid_decision_count.get(pid, 0) + 1

                    if self.pid_decision_count[pid] <= self.cold_start_threshold:
                        # Cold-start fallback: heuristic
                        heur_class = 'Heavy' if (cpu > 20 and vol_rate < 500) else 'Light'
                        action = 0 if heur_class == 'Heavy' else 1
                        decision_source = 'heuristic'
                        ucb_score = 0.0
                        self.heuristic_count += 1
                    else:
                        # Bandit selects based on UCB
                        action, ucb_score = self.bandit.select_action(context)
                        decision_source = 'bandit'
                        self.bandit_count += 1

                    latency = (time.time() - t0_inf) * 1000

                    # ── Store pending for next-cycle reward measurement ──
                    self.pending[pid] = (action, context)

                    # ── Enforce core assignment ──
                    action_label = 'P-core' if action == 0 else 'E-core'
                    target_cores = self.p_cores if action == 0 else self.e_cores
                    try:
                        p.cpu_affinity(target_cores)
                        self.history[pid]['last_switch_time'] = cycle_start
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass

                    rows.append(
                        f"{cycle_start},{pid},{true_type},{action_label},"
                        f"\"{target_cores}\",{decision_source},{cpu:.1f},"
                        f"{vol_rate:.1f},{invol_rate:.1f},{time_since_switch:.1f},"
                        f"{current_core:.1f},{reward_value:.4f},"
                        f"{self.cumulative_regret:.4f},{ucb_score:.4f},"
                        f"{self.alpha_reward},{self.beta_reward}\n"
                    )

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                except Exception as e:
                    print(f"[SCHEDULER] Error for PID {pid}: {e}")

            # ── Atomic CSV write ──
            if rows:
                log_lines = []
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, 'r') as f:
                            log_lines = f.readlines()[-300:]
                    except Exception:
                        pass
                log_lines.extend(rows)

                dir_name = os.path.dirname(os.path.abspath(LOG_FILE)) or '.'
                tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name)
                with os.fdopen(tmp_fd, 'w') as f:
                    if not log_lines or not log_lines[0].startswith("timestamp"):
                        f.write(CSV_HEADER)
                    for line in log_lines:
                        if line.startswith("timestamp"):
                            continue
                        f.write(line)
                os.replace(tmp_path, LOG_FILE)

            # Write bandit stats for dashboard
            self._write_bandit_stats()

            time.sleep(1.0)


# ─────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI-DAX Lite: LinUCB Bandit CPU Scheduler')
    parser.add_argument('--alpha', type=float, default=0.7,
                        help='Reward weight for involuntary context switches (default: 0.7)')
    parser.add_argument('--beta', type=float, default=0.3,
                        help='Reward weight for energy proxy cost (default: 0.3)')
    parser.add_argument('--exploration', type=float, default=1.5,
                        help='LinUCB exploration parameter (default: 1.5)')
    parser.add_argument('--cold-start', type=int, default=20,
                        help='Heuristic-only decisions per PID before bandit takes over (default: 20)')
    args = parser.parse_args()

    scheduler = AIScheduler(
        alpha_reward=args.alpha,
        beta_reward=args.beta,
        exploration=args.exploration,
        cold_start_threshold=args.cold_start,
    )

    def shutdown_handler(signum, frame):
        """Graceful shutdown: reset all affinities to prevent artificial core starvation."""
        print("\n[SCHEDULER] Shutting down. Resetting all affinities...")
        active = scheduler.get_active_pids()
        total_cores = os.cpu_count() or 4
        all_cores = list(range(total_cores))
        for pid, _ in active:
            try:
                p = psutil.Process(pid)
                p.cpu_affinity(all_cores)
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    scheduler.run()
