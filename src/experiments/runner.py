"""
Multi-condition experiment harness supporting baseline, heuristic, and bandit scheduling policies.
Executes real workloads, measures real task throughput iterations and context switches,
and records reproducible empirical per-trial telemetry.
"""

from __future__ import annotations

import logging
import multiprocessing
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from experiments.workloads import (
    bursty_kernel,
    cpu_intensive_kernel,
    memory_intensive_kernel,
)
from hardware.topology import CPUTopology
from process.supervisor import ProcessSupervisor
from scheduler.linucb import StableLinUCBBandit
from scheduler.reward import RewardCalculator, RewardMode
from scheduler.thompson_sampling import LinTSBandit
from telemetry.collector import TelemetryCollector

logger = logging.getLogger("aidax.experiments.runner")


@dataclass
class TrialResult:
    """Outcome metrics for a single experimental condition trial."""

    condition: str
    trial_index: int
    duration_seconds: float
    seed: int
    total_decisions: int = 0
    average_cpu_percent: float = 0.0
    average_power_watts: float = 0.0
    jain_fairness_index: float = 1.0
    energy_delay_product: float = 0.0
    total_progress_iterations: int = 0
    total_involuntary_ctx_switches: int = 0
    energy_mode: str = "ESTIMATED"
    decisions: list[dict[str, Any]] = field(default_factory=list)


class ExperimentRunner:
    """Orchestrates comparative scheduling experiments across all supported policies."""

    SUPPORTED_CONDITIONS = (
        "cfs",
        "static_p",
        "static_e",
        "round_robin",
        "heuristic",
        "random",
        "epsilon_greedy",
        "linucb",
        "thompson_sampling",
        "oracle_static",
    )

    def __init__(self, topology: CPUTopology, reward_mode: RewardMode = RewardMode.PERF) -> None:
        self.topology = topology
        self.collector = TelemetryCollector(topology=topology)
        self.reward_calculator = RewardCalculator(reward_mode=reward_mode)

    def run_condition_trial(
        self,
        condition: str,
        trial_index: int = 0,
        duration_seconds: float = 10.0,
        cycle_interval_seconds: float = 0.5,
        seed: int = 42,
    ) -> TrialResult:
        """Execute a single trial under the specified scheduling condition with fixed seed."""
        if condition not in self.SUPPORTED_CONDITIONS:
            raise ValueError(
                f"Unknown condition '{condition}'. Supported: {self.SUPPORTED_CONDITIONS}"
            )

        rng = np.random.default_rng(seed + trial_index)
        supervisor = ProcessSupervisor()
        bandit = StableLinUCBBandit(
            context_dim=4, exploration_alpha=0.5, num_arms=3, seed=seed, calibration_steps=5
        )
        ts_bandit = LinTSBandit(context_dim=4, num_arms=3, v=0.5, seed=seed)

        start_time = time.time()
        decisions: list[dict[str, Any]] = []
        cpu_samples: list[float] = []
        power_samples: list[float] = []
        fairness_samples: list[float] = []

        # Per-process tracking state
        per_proc_rr: dict[int, int] = {}
        per_proc_eps_q: dict[int, dict[int, list[float]]] = {}
        prev_iterations: dict[int, int] = {}
        prev_invol_ctx: dict[int, int] = {}

        # Shared progress counters for real work measurement
        cpu_counter = multiprocessing.Value("i", 0)
        mem_counter = multiprocessing.Value("i", 0)
        burst_counter = multiprocessing.Value("i", 0)
        counter_map: dict[int, Any] = {}

        all_cores = self.topology.p_cores + self.topology.e_cores

        logger.info(
            "Starting trial %d for condition '%s' (duration=%.1fs, seed=%d)",
            trial_index,
            condition,
            duration_seconds,
            seed,
        )

        try:
            # 1. Spawn real heterogeneous workloads
            p_cpu = supervisor.spawn_managed_worker(
                target_func=cpu_intensive_kernel,
                args=(duration_seconds + 10.0, 80, cpu_counter),
                workload_type="CPU_INTENSIVE",
                experiment_id=f"{condition}_{trial_index}",
            )
            counter_map[p_cpu.pid] = cpu_counter

            p_mem = supervisor.spawn_managed_worker(
                target_func=memory_intensive_kernel,
                args=(duration_seconds + 10.0, 16, mem_counter),
                workload_type="MEM_INTENSIVE",
                experiment_id=f"{condition}_{trial_index}",
            )
            counter_map[p_mem.pid] = mem_counter

            p_burst = supervisor.spawn_managed_worker(
                target_func=bursty_kernel,
                args=(duration_seconds + 10.0, 0.1, 0.2, burst_counter),
                workload_type="BURSTY_COMPUTE",
                experiment_id=f"{condition}_{trial_index}",
            )
            counter_map[p_burst.pid] = burst_counter

            # Wait for worker processes to begin executing (handles OS spawn latency)
            startup_deadline = time.time() + 3.0
            while time.time() < startup_deadline:
                if any(c.value > 0 for c in [cpu_counter, mem_counter, burst_counter]):
                    break
                time.sleep(0.05)

            # Record baseline counts after startup handshake
            start_time = time.time()
            prev_iterations[p_cpu.pid] = int(cpu_counter.value)
            prev_iterations[p_mem.pid] = int(mem_counter.value)
            prev_iterations[p_burst.pid] = int(burst_counter.value)

            step_count = 0
            while time.time() - start_time < duration_seconds:
                step_count += 1
                health = self.collector.sample_system_health()
                cpu_samples.append(health.total_cpu_percent)
                power_samples.append(health.estimated_power_watts)
                fairness_samples.append(health.jain_fairness_index)

                active_processes = supervisor.registry.get_valid_active_processes()

                for managed in active_processes:
                    proc_stat = self.collector.sample_managed_process(managed)
                    if not proc_stat:
                        continue

                    # Context vector x in R^4
                    context = np.array(
                        [
                            min(1.0, proc_stat.cpu_percent / 100.0),
                            min(1.0, proc_stat.memory_mb / 1024.0),
                            min(1.0, proc_stat.num_threads / 8.0),
                            1.0 if "BURSTY" in managed.workload_type else 0.0,
                        ],
                        dtype=float,
                    )

                    # Determine action based on condition
                    # 0: E-core, 1: P-core, 2: Unpinned / Kernel CFS
                    action = 2
                    pid = managed.pid

                    if condition == "cfs":
                        action = 2
                    elif condition == "static_p":
                        action = 1
                    elif condition == "static_e":
                        action = 0
                    elif condition == "round_robin":
                        rr_val = per_proc_rr.get(pid, 0)
                        action = rr_val % 3
                        per_proc_rr[pid] = rr_val + 1
                    elif condition == "heuristic":
                        if proc_stat.cpu_percent > 50.0:
                            action = 1
                        elif proc_stat.cpu_percent < 20.0:
                            action = 0
                        else:
                            action = 2
                    elif condition == "random":
                        action = int(rng.integers(0, 3))
                    elif condition == "epsilon_greedy":
                        # Per-process epsilon-greedy with decay
                        if pid not in per_proc_eps_q:
                            per_proc_eps_q[pid] = {0: [], 1: [], 2: []}
                        eps_t = max(0.05, 0.5 * (0.95**step_count))
                        if rng.random() < eps_t:
                            action = int(rng.integers(0, 3))
                        else:
                            means = [
                                float(np.mean(per_proc_eps_q[pid][a]))
                                if per_proc_eps_q[pid][a]
                                else 0.0
                                for a in range(3)
                            ]
                            action = int(np.argmax(means))
                    elif condition == "linucb":
                        action, _ = bandit.select_action(context, pid=pid)
                    elif condition == "thompson_sampling":
                        action, _ = ts_bandit.select_action(context)
                    elif condition == "oracle_static":
                        # Real hindsight oracle: offline characterized optimal assignment
                        # CPU-intensive achieves peak throughput on P-core (arm 1)
                        # Memory-bound achieves high efficiency on E-core (arm 0)
                        # Bursty tasks achieve balanced responsiveness unpinned (arm 2)
                        if "CPU" in managed.workload_type:
                            action = 1
                        elif "MEM" in managed.workload_type:
                            action = 0
                        else:
                            action = 2

                    # Apply affinity mask to target cores
                    if action == 1:
                        target_cores = self.topology.p_cores
                    elif action == 0:
                        target_cores = self.topology.e_cores
                    else:
                        target_cores = all_cores

                    supervisor.affinity_controller.set_affinity(managed, target_cores)

                    # Real progress throughput from workload shared counter
                    curr_work = 0
                    if pid in counter_map:
                        curr_work = int(counter_map[pid].value)
                    prev_work = prev_iterations.get(pid, curr_work)
                    work_delta = max(0, curr_work - prev_work)
                    prev_iterations[pid] = curr_work

                    # Real involuntary context switch delta from OS kernel
                    curr_invol = proc_stat.involuntary_ctx_switches
                    prev_invol = prev_invol_ctx.get(pid, curr_invol)
                    invol_delta = max(0, curr_invol - prev_invol)
                    prev_invol_ctx[pid] = curr_invol

                    # Multi-objective reward based on real measured work and context switches
                    reward_comps = self.reward_calculator.compute(
                        action=action,
                        progress_work_units=float(work_delta),
                        window_duration_seconds=cycle_interval_seconds,
                        invol_ctx_rate=float(invol_delta) / max(0.001, cycle_interval_seconds),
                    )
                    reward = reward_comps.total_reward

                    if pid in per_proc_eps_q:
                        per_proc_eps_q[pid][action].append(reward)

                    if condition == "linucb":
                        bandit.update(action, context, reward, pid=pid)
                    elif condition == "thompson_sampling":
                        ts_bandit.update(action, context, reward)

                    decisions.append(
                        {
                            "timestamp": time.time(),
                            "pid": managed.pid,
                            "condition": condition,
                            "action": action,
                            "work_delta": work_delta,
                            "invol_delta": invol_delta,
                            "reward": reward,
                        }
                    )

                time.sleep(cycle_interval_seconds)

        finally:
            supervisor.terminate_all()

        total_decisions = len(decisions)
        if total_decisions == 0:
            raise RuntimeError(
                f"Trial failed: zero scheduling decisions recorded for condition '{condition}'"
            )

        avg_cpu = float(np.mean(cpu_samples)) if cpu_samples else 0.0
        avg_power = float(np.mean(power_samples)) if power_samples else 0.0
        avg_fairness = float(np.mean(fairness_samples)) if fairness_samples else 1.0
        elapsed = time.time() - start_time
        edp = avg_power * (elapsed**2)

        total_iterations = sum(d["work_delta"] for d in decisions)
        total_invol = sum(d["invol_delta"] for d in decisions)

        return TrialResult(
            condition=condition,
            trial_index=trial_index,
            duration_seconds=elapsed,
            seed=seed,
            total_decisions=total_decisions,
            average_cpu_percent=round(avg_cpu, 2),
            average_power_watts=round(avg_power, 2),
            jain_fairness_index=round(avg_fairness, 4),
            energy_delay_product=round(edp, 2),
            total_progress_iterations=total_iterations,
            total_involuntary_ctx_switches=total_invol,
            energy_mode="ESTIMATED",
            decisions=decisions,
        )
