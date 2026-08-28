"""
AI-DAX Lite: Four-Condition Evaluation Harness
===============================================
Runs the SAME workload under four scheduling conditions for rigorous
comparative evaluation. Each condition is repeated N trials (default 5).

Conditions:
  1. baseline_cfs    — No affinity calls at all (pure OS CFS scheduling)
  2. static_naive    — Fixed rule: Heavy→P-core, Light→E-core, no learning
  3. heuristic_only  — The cold-start heuristic with learning disabled
  4. bandit_adaptive — Full LinUCB bandit from ai_scheduler.py

Outputs: results.csv (one row per trial)
"""

import os
import sys
import time
import json
import csv
import signal
import argparse
import multiprocessing
import psutil
import tempfile
import numpy as np

# Import from project modules
from workload_generator import spawn_workload, PID_FILE


def get_active_pids_safe():
    """Read PIDs with safety checks (mirrors scheduler logic)."""
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
                    if (p.create_time() == start_time and
                            p.username() == psutil.Process().username()):
                        active.append((pid, data['type']))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return active


def detect_cores():
    """Split cores 50/50 (mirrors scheduler fallback)."""
    total = os.cpu_count() or 4
    half = total // 2
    return list(range(half)), list(range(half, total))


def reset_all_affinities():
    """Reset all tracked processes to use all cores."""
    total = os.cpu_count() or 4
    all_cores = list(range(total))
    for pid, _ in get_active_pids_safe():
        try:
            p = psutil.Process(pid)
            p.cpu_affinity(all_cores)
        except Exception:
            pass


def collect_metrics(pids_info, duration_s, sample_interval=1.0):
    """
    Collect per-process metrics over the given duration.
    Returns list of dicts with per-process stats.
    """
    # Prime psutil CPU measurement
    procs = {}
    for pid, ptype in pids_info:
        try:
            p = psutil.Process(pid)
            p.cpu_percent(interval=None)
            procs[pid] = {'type': ptype, 'proc': p, 'cpu_samples': [],
                          'invol_ctx': [], 'vol_ctx': []}
        except Exception:
            pass

    start = time.time()
    completion_times = {}
    while time.time() - start < duration_s:
        all_dead = True
        for pid, info in procs.items():
            try:
                p = info['proc']
                if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                    if pid not in completion_times:
                        completion_times[pid] = time.time() - start
                    continue
                all_dead = False
                info['cpu_samples'].append(p.cpu_percent(interval=0.0))
                ctx = p.num_ctx_switches()
                info['invol_ctx'].append(ctx.involuntary)
                info['vol_ctx'].append(ctx.voluntary)
            except Exception:
                if pid not in completion_times:
                    completion_times[pid] = time.time() - start
                
        if all_dead:
            break
        time.sleep(sample_interval)

    # For any still running, mark completion time as duration_s
    for pid in procs.keys():
        if pid not in completion_times:
            completion_times[pid] = duration_s


    results = []
    for pid, info in procs.items():
        cpu_samples = info['cpu_samples']
        invol_samples = info['invol_ctx']
        if len(cpu_samples) < 2:
            continue
        results.append({
            'pid': pid,
            'type': info['type'],
            'mean_cpu': np.mean(cpu_samples),
            'median_cpu': np.median(cpu_samples),
            'p95_cpu': np.percentile(cpu_samples, 95) if len(cpu_samples) > 1 else 0,
            'mean_invol_ctx': np.mean(np.diff(invol_samples)) if len(invol_samples) > 1 else 0,
            'median_invol_ctx': np.median(np.diff(invol_samples)) if len(invol_samples) > 1 else 0,
            'p95_invol_ctx': np.percentile(np.diff(invol_samples), 95) if len(invol_samples) > 2 else 0,
            'total_cpu_time': sum(cpu_samples),
            'completion_time': completion_times[pid],
        })
    return results


def run_condition_baseline_cfs(duration, n_heavy, m_light):
    """Condition 1: No affinity manipulation at all. Pure CFS."""
    print(f"  [CFS] Running baseline for {duration}s...")
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)  # let processes stabilise
    pids_info = get_active_pids_safe()
    metrics = collect_metrics(pids_info, duration)
    # Cleanup
    for p, _ in spawned:
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
    return metrics


def run_condition_static_naive(duration, n_heavy, m_light):
    """Condition 2: Fixed rule — Heavy→P, Light→E, no learning."""
    print(f"  [STATIC] Running static naive for {duration}s...")
    p_cores, e_cores = detect_cores()
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)

    pids_info = get_active_pids_safe()
    # Apply static assignment once
    for pid, ptype in pids_info:
        try:
            p = psutil.Process(pid)
            target = p_cores if ptype == 'Heavy' else e_cores
            p.cpu_affinity(target)
        except Exception:
            pass

    metrics = collect_metrics(pids_info, duration)
    reset_all_affinities()
    for p, _ in spawned:
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
    return metrics


def run_condition_heuristic_only(duration, n_heavy, m_light):
    """Condition 3: Heuristic classification only, no bandit learning."""
    print(f"  [HEURISTIC] Running heuristic-only for {duration}s...")
    p_cores, e_cores = detect_cores()
    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)

    pids_info = get_active_pids_safe()
    # Prime CPU measurements
    proc_map = {}
    for pid, ptype in pids_info:
        try:
            p = psutil.Process(pid)
            p.cpu_percent(interval=None)
            proc_map[pid] = {'type': ptype, 'proc': p}
        except Exception:
            pass

    start = time.time()
    while time.time() - start < duration:
        for pid, info in proc_map.items():
            try:
                p = info['proc']
                if not p.is_running():
                    continue
                cpu = p.cpu_percent(interval=0.0)
                ctx = p.num_ctx_switches()
                dt = 1.0
                vol_rate = ctx.voluntary / max(time.time() - start, 1)
                heur = 'Heavy' if (cpu > 20 and vol_rate < 500) else 'Light'
                target = p_cores if heur == 'Heavy' else e_cores
                p.cpu_affinity(target)
            except Exception:
                pass
        time.sleep(1.0)

    # Collect final metrics
    metrics = collect_metrics(pids_info, min(duration, 10))
    reset_all_affinities()
    for p, _ in spawned:
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
    return metrics


def run_condition_bandit(duration, n_heavy, m_light, alpha, beta, exploration):
    """Condition 4: Full LinUCB bandit from ai_scheduler.py."""
    print(f"  [BANDIT] Running LinUCB bandit for {duration}s...")
    from ai_scheduler import AIScheduler
    import threading

    spawned = spawn_workload(n_heavy=n_heavy, m_light=m_light, finite=True)
    time.sleep(2)

    scheduler = AIScheduler(
        alpha_reward=alpha,
        beta_reward=beta,
        exploration=exploration,
        cold_start_threshold=10,  # shorter cold-start for eval
    )

    # Run scheduler in a thread
    stop_event = threading.Event()

    def scheduler_loop():
        while not stop_event.is_set():
            try:
                cycle_start = time.time()
                active = scheduler.get_active_pids()
                for pid, true_type in active:
                    try:
                        p = psutil.Process(pid)
                        cpu = p.cpu_percent(interval=0.0)
                        ctx = p.num_ctx_switches()

                        if pid not in scheduler.history:
                            p.cpu_percent(interval=None)
                            scheduler.history[pid] = {
                                'vol': ctx.voluntary,
                                'invol': ctx.involuntary,
                                'time': cycle_start,
                                'last_switch_time': cycle_start,
                            }
                            scheduler.pid_decision_count[pid] = 0
                            continue

                        dt = cycle_start - scheduler.history[pid]['time']
                        if dt <= 0:
                            continue

                        vol_rate = (ctx.voluntary - scheduler.history[pid]['vol']) / dt
                        invol_rate = (ctx.involuntary - scheduler.history[pid]['invol']) / dt
                        time_since_switch = cycle_start - scheduler.history[pid]['last_switch_time']
                        current_core = scheduler._get_current_core_assignment(pid)

                        scheduler.history[pid]['vol'] = ctx.voluntary
                        scheduler.history[pid]['invol'] = ctx.involuntary
                        scheduler.history[pid]['time'] = cycle_start

                        raw_context = np.array([
                            cpu, vol_rate, invol_rate, time_since_switch, current_core
                        ])
                        scheduler.scaler.update(raw_context)
                        context = scheduler.scaler.transform(raw_context)

                        # Process pending reward
                        if pid in scheduler.pending:
                            prev_action, prev_context = scheduler.pending[pid]
                            reward = scheduler._compute_reward(prev_action, invol_rate)
                            scheduler.bandit.update(prev_action, prev_context, reward)

                        # Decision
                        scheduler.pid_decision_count[pid] = \
                            scheduler.pid_decision_count.get(pid, 0) + 1
                        if scheduler.pid_decision_count[pid] <= scheduler.cold_start_threshold:
                            heur = 'Heavy' if (cpu > 20 and vol_rate < 500) else 'Light'
                            action = 0 if heur == 'Heavy' else 1
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

    # Collect metrics
    pids_info = get_active_pids_safe()
    metrics = collect_metrics(pids_info, duration)

    stop_event.set()
    t.join(timeout=5)
    reset_all_affinities()
    for p, _ in spawned:
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
    return metrics


def compute_jain_fairness(cpu_times):
    """Jain's Fairness Index: J = (sum(x_i))^2 / (n * sum(x_i^2))"""
    if not cpu_times or len(cpu_times) == 0:
        return 0.0
    x = np.array(cpu_times, dtype=float)
    n = len(x)
    if n == 0 or np.sum(x ** 2) == 0:
        return 0.0
    return (np.sum(x) ** 2) / (n * np.sum(x ** 2))


def aggregate_metrics(process_metrics):
    """Aggregate per-process metrics into trial-level stats."""
    if not process_metrics:
        return {
            'mean_cpu': 0, 'mean_invol_ctx': 0, 'median_invol_ctx': 0,
            'p95_invol_ctx': 0, 'jain_fairness': 0, 'n_processes': 0,
            'mean_completion_time': 0, 'heavy_task_completion_time': 0,
        }
    heavy_metrics = [m for m in process_metrics if m['type'] == 'Heavy']
    mean_completion = np.mean([m['completion_time'] for m in process_metrics]) if process_metrics else 0
    heavy_completion = np.mean([m['completion_time'] for m in heavy_metrics]) if heavy_metrics else 0

    return {
        'mean_cpu': np.mean([m['mean_cpu'] for m in process_metrics]),
        'mean_invol_ctx': np.mean([m['mean_invol_ctx'] for m in process_metrics]),
        'median_invol_ctx': np.median([m['median_invol_ctx'] for m in process_metrics]),
        'p95_invol_ctx': np.mean([m['p95_invol_ctx'] for m in process_metrics]),
        'jain_fairness': compute_jain_fairness(
            [m['total_cpu_time'] for m in process_metrics]
        ),
        'n_processes': len(process_metrics),
        'mean_completion_time': mean_completion,
        'heavy_task_completion_time': heavy_completion,
    }


def main():
    parser = argparse.ArgumentParser(
        description='AI-DAX Lite: Four-Condition Evaluation Harness')
    parser.add_argument('--duration', type=int, default=60,
                        help='Duration per condition in seconds (default: 60)')
    parser.add_argument('--trials', type=int, default=5,
                        help='Number of trials per condition (default: 5)')
    parser.add_argument('--heavy', type=int, default=2,
                        help='Number of heavy workers (default: 2)')
    parser.add_argument('--light', type=int, default=2,
                        help='Number of light workers (default: 2)')
    parser.add_argument('--alpha', type=float, default=0.7,
                        help='Bandit reward alpha (default: 0.7)')
    parser.add_argument('--beta', type=float, default=0.3,
                        help='Bandit reward beta (default: 0.3)')
    parser.add_argument('--exploration', type=float, default=1.5,
                        help='LinUCB exploration (default: 1.5)')
    parser.add_argument('--output', type=str, default='results.csv',
                        help='Output CSV path (default: results.csv)')
    args = parser.parse_args()

    conditions = [
        ('baseline_cfs', lambda: run_condition_baseline_cfs(
            args.duration, args.heavy, args.light)),
        ('static_naive', lambda: run_condition_static_naive(
            args.duration, args.heavy, args.light)),
        ('heuristic_only', lambda: run_condition_heuristic_only(
            args.duration, args.heavy, args.light)),
        ('bandit_adaptive', lambda: run_condition_bandit(
            args.duration, args.heavy, args.light,
            args.alpha, args.beta, args.exploration)),
    ]

    results = []

    for cond_name, cond_fn in conditions:
        print(f"\n{'='*60}")
        print(f"  CONDITION: {cond_name}")
        print(f"{'='*60}")
        for trial in range(1, args.trials + 1):
            print(f"\n  Trial {trial}/{args.trials}")
            # Clean PID file between trials
            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except OSError:
                    pass
            if os.path.exists('scheduler_log.csv'):
                try:
                    os.remove('scheduler_log.csv')
                except OSError:
                    pass

            try:
                process_metrics = cond_fn()
                agg = aggregate_metrics(process_metrics)
                row = {
                    'condition': cond_name,
                    'trial': trial,
                    'duration_s': args.duration,
                    'n_heavy': args.heavy,
                    'n_light': args.light,
                    'mean_cpu_pct': round(agg['mean_cpu'], 2),
                    'mean_invol_ctx_switches': round(agg['mean_invol_ctx'], 2),
                    'median_invol_ctx_switches': round(agg['median_invol_ctx'], 2),
                    'p95_invol_ctx_switches': round(agg['p95_invol_ctx'], 2),
                    'jain_fairness_index': round(agg['jain_fairness'], 4),
                    'mean_completion_time': round(agg['mean_completion_time'], 2),
                    'heavy_task_completion_time': round(agg['heavy_task_completion_time'], 2),
                    'n_processes_measured': agg['n_processes'],
                }
                results.append(row)
                print(f"    Mean CPU: {agg['mean_cpu']:.1f}% | "
                      f"Mean Invol Ctx: {agg['mean_invol_ctx']:.1f} | "
                      f"Jain: {agg['jain_fairness']:.4f} | "
                      f"Heavy Comp Time: {agg['heavy_task_completion_time']:.2f}s")
            except Exception as e:
                print(f"    ERROR in trial: {e}")
                results.append({
                    'condition': cond_name, 'trial': trial,
                    'duration_s': args.duration, 'error': str(e),
                })

            # Cooldown between trials
            time.sleep(3)

    # Write results.csv
    if results:
        fieldnames = list(results[0].keys())
        with open(args.output, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[DONE] Results written to {args.output}")
    else:
        print("\n[WARN] No results collected.")


if __name__ == '__main__':
    main()
