"""
Multi-condition experiment harness supporting baseline, heuristic, and bandit scheduling policies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

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
    throughput_iterations: int = 0
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
        bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0, num_arms=3, seed=seed)
        ts_bandit = LinTSBandit(context_dim=4, num_arms=3, v=0.5, seed=seed)

        start_time = time.time()
        decisions: list[dict[str, Any]] = []
        cpu_samples: list[float] = []
        power_samples: list[float] = []
        fairness_samples: list[float] = []
        rr_step = 0
        eps_running_rewards: dict[int, list[float]] = {0: [], 1: [], 2: []}

        all_cores = self.topology.p_cores + self.topology.e_cores

        logger.info(
            "Starting trial %d for condition '%s' (duration=%.1fs, seed=%d)",
            trial_index,
            condition,
            duration_seconds,
            seed,
        )

        try:
            while time.time() - start_time < duration_seconds:
                health = self.collector.sample_system_health()
                cpu_samples.append(health.total_cpu_percent)
                power_samples.append(health.estimated_power_watts)
                fairness_samples.append(health.jain_fairness_index)

                active_processes = supervisor.registry.get_valid_active_processes()

                for managed in active_processes:
                    proc_stat = self.collector.sample_managed_process(managed)
                    if not proc_stat:
                        continue

                    # Context: [cpu_pct/100, mem_mb/1024, threads/8, is_bursty]
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
                    # 0: E-core, 1: P-core, 2: Unpinned (all cores)
                    action = 2
                    if condition == "cfs":
                        action = 2
                    elif condition == "static_p":
                        action = 1
                    elif condition == "static_e":
                        action = 0
                    elif condition == "round_robin":
                        action = rr_step % 3
                        rr_step += 1
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
                        if rng.random() < 0.1:
                            action = int(rng.integers(0, 3))
                        else:
                            means = [
                                float(np.mean(eps_running_rewards[a]))
                                if eps_running_rewards[a]
                                else 0.0
                                for a in range(3)
                            ]
                            action = int(np.argmax(means))
                    elif condition == "linucb":
                        action, _ = bandit.select_action(context)
                    elif condition == "thompson_sampling":
                        action, _ = ts_bandit.select_action(context)
                    elif condition == "oracle_static":
                        # Offline best static assignment per workload (hindsight oracle reference)
                        if "CPU" in managed.workload_type:
                            action = 1
                        elif "MEM" in managed.workload_type:
                            action = 0
                        else:
                            action = 2

                    # Map action to core set
                    if action == 1:
                        target_cores = self.topology.p_cores
                    elif action == 0:
                        target_cores = self.topology.e_cores
                    else:
                        target_cores = all_cores

                    supervisor.affinity_controller.set_affinity(managed, target_cores)

                    # Online feedback calculation
                    reward_comps = self.reward_calculator.compute(
                        action=action,
                        progress_work_units=proc_stat.cpu_percent * 2.0,
                        window_duration_seconds=cycle_interval_seconds,
                        invol_ctx_rate=proc_stat.cpu_percent * 5.0,
                    )
                    reward = reward_comps.total_reward
                    eps_running_rewards[action].append(reward)

                    if condition == "linucb":
                        bandit.update(action, context, reward)
                    elif condition == "thompson_sampling":
                        ts_bandit.update(action, context, reward)

                    decisions.append(
                        {
                            "timestamp": time.time(),
                            "pid": managed.pid,
                            "condition": condition,
                            "action": action,
                            "reward": reward,
                        }
                    )

                time.sleep(cycle_interval_seconds)

        finally:
            supervisor.terminate_all()

        avg_cpu = float(np.mean(cpu_samples)) if cpu_samples else 0.0
        avg_power = float(np.mean(power_samples)) if power_samples else 0.0
        avg_fairness = float(np.mean(fairness_samples)) if fairness_samples else 1.0
        elapsed = time.time() - start_time
        edp = avg_power * (elapsed**2)

        return TrialResult(
            condition=condition,
            trial_index=trial_index,
            duration_seconds=elapsed,
            seed=seed,
            total_decisions=len(decisions),
            average_cpu_percent=round(avg_cpu, 2),
            average_power_watts=round(avg_power, 2),
            jain_fairness_index=round(avg_fairness, 4),
            energy_delay_product=round(edp, 2),
            decisions=decisions,
        )
