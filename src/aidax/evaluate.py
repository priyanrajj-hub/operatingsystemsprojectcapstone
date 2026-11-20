"""
AI-DAX Lite: Four-Condition Evaluation Harness
===============================================
Runs identical workloads under four scheduling conditions for empirical
comparative evaluation:

Conditions:
  1. baseline_cfs    — Default OS CFS scheduling (no affinity pinning)
  2. static_naive    — Static rule: Heavy->P-core, Light->E-core, zero learning
  3. heuristic_only  — Cold-start rule-based heuristic with learning disabled
  4. bandit_adaptive — Full LinUCB contextual bandit from aidax.scheduler

Outputs: results.csv (one row per condition trial)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import psutil

from aidax.scheduler import AIScheduler, SchedulerConfig
from aidax.workload import PID_FILE, spawn_workload, terminate_workers

logger = logging.getLogger("aidax.evaluate")


def get_active_pids_safe(pid_file: str = PID_FILE) -> list[tuple[int, str]]:
    """Read active target processes with creation-time verification."""
    active: list[tuple[int, str]] = []
    if not os.path.exists(pid_file):
        return active

    current_username: str | None = None
    try:
        current_username = psutil.Process().username()
    except Exception:
        pass

    try:
        with open(pid_file, encoding="utf-8") as f:
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
                except (psutil.NoSuchProcess, psutil.AccessDenied, json.JSONDecodeError, KeyError):
                    continue
    except FileNotFoundError:
        pass
    return active


def detect_cores() -> tuple[list[int], list[int]]:
    """Determine P-core / E-core assignment fallback (50/50 split)."""
    total = os.cpu_count() or 4
    half = max(1, total // 2)
    return list(range(half)), list(range(half, total))


def reset_all_affinities(pid_file: str = PID_FILE) -> None:
    """Reset all tracked processes to utilize all available CPU cores."""
    total = os.cpu_count() or 4
    all_cores = list(range(total))
    for pid, _ in get_active_pids_safe(pid_file):
        try:
            p = psutil.Process(pid)
            p.cpu_affinity(all_cores)
        except Exception:
            pass


def collect_metrics(
    pids_info: list[tuple[int, str]],
    duration_s: float,
    sample_interval: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Collect per-process CPU percentage and context switch metrics over duration_s.
    """
    procs: dict[int, dict[str, Any]] = {}
    for pid, ptype in pids_info:
        try:
            p = psutil.Process(pid)
            p.cpu_percent(interval=None)
            procs[pid] = {
                "type": ptype,
                "proc": p,
                "cpu_samples": [],
                "invol_ctx": [],
                "vol_ctx": [],
            }
        except Exception:
            pass

    start = time.time()
    completion_times: dict[int, float] = {}

    while time.time() - start < duration_s:
        all_dead = True
        for pid, info in procs.items():
            try:
                p = info["proc"]
                if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                    if pid not in completion_times:
                        completion_times[pid] = time.time() - start
                    continue

                all_dead = False
                info["cpu_samples"].append(p.cpu_percent(interval=0.0))
                ctx = p.num_ctx_switches()
                info["invol_ctx"].append(ctx.involuntary)
                info["vol_ctx"].append(ctx.voluntary)
            except Exception:
                if pid not in completion_times:
                    completion_times[pid] = time.time() - start

        if all_dead:
            break
        time.sleep(sample_interval)

    for pid in procs:
        if pid not in completion_times:
            completion_times[pid] = duration_s

    results: list[dict[str, Any]] = []
    for pid, info in procs.items():
        cpu_samples = info["cpu_samples"]
        invol_samples = info["invol_ctx"]
        if len(cpu_samples) < 2:
            continue
        results.append(
            {
                "pid": pid,
                "type": info["type"],
                "mean_cpu": float(np.mean(cpu_samples)),
                "median_cpu": float(np.median(cpu_samples)),
                "p95_cpu": float(np.percentile(cpu_samples, 95)) if len(cpu_samples) > 1 else 0.0,
                "mean_invol_ctx": float(np.mean(np.diff(invol_samples)))
                if len(invol_samples) > 1
                else 0.0,
                "median_invol_ctx": float(np.median(np.diff(invol_samples)))
                if len(invol_samples) > 1
                else 0.0,
                "p95_invol_ctx": float(np.percentile(np.diff(invol_samples), 95))
                if len(invol_samples) > 2
                else 0.0,
                "total_cpu_time": float(sum(cpu_samples)),
                "completion_time": float(completion_times[pid]),
            }
        )
    return results


def run_condition_baseline_cfs(
    duration: int,
    n_heavy: int,
    m_light: int,
) -> list[dict[str, Any]]:
    """Condition 1: Pure OS Completely Fair Scheduler (no affinity calls)."""
    logger.info("[CFS] Running baseline for %ds...", duration)
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)
    pids_info = get_active_pids_safe()
    metrics = collect_metrics(pids_info, duration)
    terminate_workers([p for p, _ in spawned])
    return metrics


def run_condition_static_naive(
    duration: int,
    n_heavy: int,
    m_light: int,
) -> list[dict[str, Any]]:
    """Condition 2: Fixed heuristic allocation (Heavy->P-cores, Light->E-cores)."""
    logger.info("[STATIC] Running static naive for %ds...", duration)
    p_cores, e_cores = detect_cores()
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)

    pids_info = get_active_pids_safe()
    for pid, ptype in pids_info:
        try:
            p = psutil.Process(pid)
            target = p_cores if ptype == "Heavy" else e_cores
            p.cpu_affinity(target)
        except Exception:
            pass

    metrics = collect_metrics(pids_info, duration)
    reset_all_affinities()
    terminate_workers([p for p, _ in spawned])
    return metrics


def run_condition_heuristic_only(
    duration: int,
    n_heavy: int,
    m_light: int,
) -> list[dict[str, Any]]:
    """Condition 3: Dynamic heuristic classification without contextual bandit learning."""
    logger.info("[HEURISTIC] Running heuristic-only for %ds...", duration)
    p_cores, e_cores = detect_cores()
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)

    pids_info = get_active_pids_safe()
    proc_map: dict[int, dict[str, Any]] = {}
    for pid, ptype in pids_info:
        try:
            p = psutil.Process(pid)
            p.cpu_percent(interval=None)
            proc_map[pid] = {"type": ptype, "proc": p}
        except Exception:
            pass

    start = time.time()
    while time.time() - start < duration:
        for _pid, info in proc_map.items():
            try:
                p = info["proc"]
                if not p.is_running():
                    continue
                cpu = p.cpu_percent(interval=0.0)
                ctx = p.num_ctx_switches()
                vol_rate = ctx.voluntary / max(time.time() - start, 1.0)
                heur = "Heavy" if (cpu > 20 and vol_rate < 500) else "Light"
                target = p_cores if heur == "Heavy" else e_cores
                p.cpu_affinity(target)
            except Exception:
                pass
        time.sleep(1.0)

    metrics = collect_metrics(pids_info, min(duration, 10))
    reset_all_affinities()
    terminate_workers([p for p, _ in spawned])
    return metrics


def run_condition_bandit(
    duration: int,
    n_heavy: int,
    m_light: int,
    alpha: float,
    beta: float,
    exploration: float,
) -> list[dict[str, Any]]:
    """Condition 4: Full online LinUCB contextual bandit adaptation."""
    logger.info("[BANDIT] Running LinUCB bandit for %ds...", duration)
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)

    config = SchedulerConfig(
        alpha_reward=alpha,
        beta_reward=beta,
        exploration=exploration,
        cold_start_threshold=10,
    )
    scheduler = AIScheduler(config=config)

    stop_event = threading.Event()

    def scheduler_loop() -> None:
        while not stop_event.is_set():
            try:
                cycle_start = time.time()
                active = scheduler.get_active_pids()
                for pid, _true_type in active:
                    try:
                        p = psutil.Process(pid)
                        cpu = p.cpu_percent(interval=0.0)
                        ctx = p.num_ctx_switches()

                        if pid not in scheduler.history:
                            p.cpu_percent(interval=None)
                            scheduler.history[pid] = {
                                "vol": ctx.voluntary,
                                "invol": ctx.involuntary,
                                "time": cycle_start,
                                "last_switch_time": cycle_start,
                            }
                            scheduler.pid_decision_count[pid] = 0
                            continue

                        dt = cycle_start - scheduler.history[pid]["time"]
                        if dt <= 0:
                            continue

                        vol_rate = (ctx.voluntary - scheduler.history[pid]["vol"]) / dt
                        invol_rate = (ctx.involuntary - scheduler.history[pid]["invol"]) / dt
                        time_since_switch = cycle_start - scheduler.history[pid]["last_switch_time"]
                        current_core = scheduler._get_current_core_assignment(pid)

                        scheduler.history[pid]["vol"] = ctx.voluntary
                        scheduler.history[pid]["invol"] = ctx.involuntary
                        scheduler.history[pid]["time"] = cycle_start

                        raw_context = np.array(
                            [cpu, vol_rate, invol_rate, time_since_switch, current_core],
                            dtype=float,
                        )
                        scheduler.scaler.update(raw_context)
                        context = scheduler.scaler.transform(raw_context)

                        if pid in scheduler.pending:
                            prev_action, prev_context = scheduler.pending[pid]
                            reward = scheduler._compute_reward(prev_action, invol_rate)
                            scheduler.bandit.update(prev_action, prev_context, reward)

                        scheduler.pid_decision_count[pid] = (
                            scheduler.pid_decision_count.get(pid, 0) + 1
                        )
                        if scheduler.pid_decision_count[pid] <= scheduler.cold_start_threshold:
                            heur = "Heavy" if (cpu > 20 and vol_rate < 500) else "Light"
                            action = 0 if heur == "Heavy" else 1
                        else:
                            action, _ = scheduler.bandit.select_action(context)

                        scheduler.pending[pid] = (action, context)
                        target = scheduler.p_cores if action == 0 else scheduler.e_cores
                        try:
                            p.cpu_affinity(target)
                        except Exception:
                            pass
                    except Exception:
                        pass
                time.sleep(1.0)
            except Exception:
                time.sleep(1.0)

    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

    pids_info = get_active_pids_safe()
    metrics = collect_metrics(pids_info, duration)

    stop_event.set()
    t.join(timeout=5)
    reset_all_affinities()
    terminate_workers([p for p, _ in spawned])
    return metrics


def compute_jain_fairness(cpu_times: list[float]) -> float:
    """
    Calculate Jain's Fairness Index:
    J = (sum(x_i))^2 / (n * sum(x_i^2))
    """
    if not cpu_times:
        return 0.0
    x = np.array(cpu_times, dtype=float)
    n = len(x)
    sum_sq = float(np.sum(x**2))
    if n == 0 or sum_sq == 0.0:
        return 0.0
    return float((np.sum(x) ** 2) / (n * sum_sq))


def aggregate_metrics(process_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate process-level metric records into trial summary metrics."""
    if not process_metrics:
        return {
            "mean_cpu": 0.0,
            "mean_invol_ctx": 0.0,
            "median_invol_ctx": 0.0,
            "p95_invol_ctx": 0.0,
            "jain_fairness": 0.0,
            "n_processes": 0,
            "mean_completion_time": 0.0,
            "heavy_task_completion_time": 0.0,
        }

    heavy_metrics = [m for m in process_metrics if m["type"] == "Heavy"]
    mean_completion = float(np.mean([m["completion_time"] for m in process_metrics]))
    heavy_completion = (
        float(np.mean([m["completion_time"] for m in heavy_metrics])) if heavy_metrics else 0.0
    )

    return {
        "mean_cpu": float(np.mean([m["mean_cpu"] for m in process_metrics])),
        "mean_invol_ctx": float(np.mean([m["mean_invol_ctx"] for m in process_metrics])),
        "median_invol_ctx": float(np.median([m["median_invol_ctx"] for m in process_metrics])),
        "p95_invol_ctx": float(np.mean([m["p95_invol_ctx"] for m in process_metrics])),
        "jain_fairness": compute_jain_fairness([m["total_cpu_time"] for m in process_metrics]),
        "n_processes": len(process_metrics),
        "mean_completion_time": mean_completion,
        "heavy_task_completion_time": heavy_completion,
    }


def evaluate(
    duration: int = 60,
    trials: int = 5,
    n_heavy: int = 2,
    m_light: int = 2,
    alpha: float = 0.7,
    beta: float = 0.3,
    exploration: float = 1.5,
    output_path: str = "results.csv",
) -> list[dict[str, Any]]:
    """Execute the full multi-condition comparative evaluation benchmark."""
    conditions: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = [
        ("baseline_cfs", lambda: run_condition_baseline_cfs(duration, n_heavy, m_light)),
        ("static_naive", lambda: run_condition_static_naive(duration, n_heavy, m_light)),
        ("heuristic_only", lambda: run_condition_heuristic_only(duration, n_heavy, m_light)),
        (
            "bandit_adaptive",
            lambda: run_condition_bandit(duration, n_heavy, m_light, alpha, beta, exploration),
        ),
    ]

    results: list[dict[str, Any]] = []

    for cond_name, cond_fn in conditions:
        print(f"\n{'=' * 60}\n  CONDITION: {cond_name}\n{'=' * 60}")
        for trial in range(1, trials + 1):
            print(f"\n  Trial {trial}/{trials}")
            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except OSError:
                    pass
            if os.path.exists("scheduler_log.csv"):
                try:
                    os.remove("scheduler_log.csv")
                except OSError:
                    pass

            try:
                process_metrics = cond_fn()
                agg = aggregate_metrics(process_metrics)
                row = {
                    "condition": cond_name,
                    "trial": trial,
                    "duration_s": duration,
                    "n_heavy": n_heavy,
                    "n_light": m_light,
                    "mean_cpu_pct": round(agg["mean_cpu"], 2),
                    "mean_invol_ctx_switches": round(agg["mean_invol_ctx"], 2),
                    "median_invol_ctx_switches": round(agg["median_invol_ctx"], 2),
                    "p95_invol_ctx_switches": round(agg["p95_invol_ctx"], 2),
                    "jain_fairness_index": round(agg["jain_fairness"], 4),
                    "mean_completion_time": round(agg["mean_completion_time"], 2),
                    "heavy_task_completion_time": round(agg["heavy_task_completion_time"], 2),
                    "n_processes_measured": agg["n_processes"],
                }
                results.append(row)
                print(
                    f"    Mean CPU: {agg['mean_cpu']:.1f}% | "
                    f"Mean Invol Ctx: {agg['mean_invol_ctx']:.1f} | "
                    f"Jain: {agg['jain_fairness']:.4f} | "
                    f"Heavy Comp Time: {agg['heavy_task_completion_time']:.2f}s"
                )
            except Exception as e:
                logger.error("Error in trial %d of %s: %s", trial, cond_name, e)
                results.append(
                    {
                        "condition": cond_name,
                        "trial": trial,
                        "duration_s": duration,
                        "error": str(e),
                    }
                )

            time.sleep(3)

    if results:
        dir_name = os.path.dirname(os.path.abspath(output_path))
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        fieldnames = list(results[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[DONE] Results written to {output_path}")
    else:
        print("\n[WARN] No results collected.")

    return results


def main() -> None:
    """CLI entry point for aidax-eval."""
    parser = argparse.ArgumentParser(description="AI-DAX Lite: Four-Condition Evaluation Harness")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration per condition in seconds (default: 60)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Number of trials per condition (default: 5)",
    )
    parser.add_argument(
        "--heavy",
        type=int,
        default=2,
        help="Number of heavy workers (default: 2)",
    )
    parser.add_argument(
        "--light",
        type=int,
        default=2,
        help="Number of light workers (default: 2)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.7,
        help="Bandit reward alpha weight (default: 0.7)",
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=0.3,
        help="Bandit reward beta weight (default: 0.3)",
    )
    parser.add_argument(
        "--exploration",
        type=float,
        default=1.5,
        help="LinUCB exploration parameter (default: 1.5)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results.csv",
        help="Output CSV path (default: results.csv)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    )

    evaluate(
        duration=args.duration,
        trials=args.trials,
        n_heavy=args.heavy,
        m_light=args.light,
        alpha=args.alpha,
        beta=args.beta,
        exploration=args.exploration,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
