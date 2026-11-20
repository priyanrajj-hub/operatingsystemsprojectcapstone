"""
Multi-condition experiment harness supporting all 7 baseline and bandit scheduling policies.
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
from scheduler.reward import RewardCalculator
from scheduler.thompson_sampling import LinTSBandit
from telemetry.collector import TelemetryCollector

logger = logging.getLogger("aidax.experiments.runner")


@dataclass
class TrialResult:
    """Outcome metrics for a single experimental condition trial."""

    condition: str
    trial_index: int
    duration_seconds: float
    total_decisions: int = 0
    average_cpu_percent: float = 0.0
    average_power_watts: float = 0.0
    jain_fairness_index: float = 1.0
    energy_delay_product: float = 0.0
    throughput_iterations: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)


class ExperimentRunner:
    """Orchestrates comparative scheduling experiments across all 7 supported policies."""

    SUPPORTED_CONDITIONS = (
        "cfs",
        "static_p",
        "static_e",
        "round_robin",
        "heuristic",
        "linucb",
        "thompson_sampling",
    )

    def __init__(self, topology: CPUTopology) -> None:
        self.topology = topology
        self.collector = TelemetryCollector(topology=topology)
        self.reward_calculator = RewardCalculator()

    def run_condition_trial(
        self,
        condition: str,
        trial_index: int = 0,
        duration_seconds: float = 10.0,
        cycle_interval_seconds: float = 0.5,
    ) -> TrialResult:
        """Execute a single trial under the specified scheduling condition."""
        if condition not in self.SUPPORTED_CONDITIONS:
            raise ValueError(f"Unknown condition '{condition}'. Supported: {self.SUPPORTED_CONDITIONS}")

        supervisor = ProcessSupervisor()
        bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0)
        ts_bandit = LinTSBandit(context_dim=4, v=0.5)

        start_time = time.time()
        decisions: list[dict[str, Any]] = []
        cpu_samples: list[float] = []
        power_samples: list[float] = []
        fairness_samples: list[float] = []
        rr_toggle = 0

        logger.info("Starting trial %d for condition '%s' (duration=%.1fs)", trial_index, condition, duration_seconds)

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
                    context = np.array([
                        min(1.0, proc_stat.cpu_percent / 100.0),
                        min(1.0, proc_stat.memory_mb / 1024.0),
                        min(1.0, proc_stat.num_threads / 8.0),
                        1.0 if "BURSTY" in managed.workload_type else 0.0,
                    ], dtype=float)

                    # Determine action based on condition
                    target_cores: list[int] = []
                    action = 0

                    if condition == "cfs":
                        # Native OS CFS: unconstrained full affinity
                        target_cores = self.topology.p_cores + self.topology.e_cores
                        action = 1
                    elif condition == "static_p":
                        target_cores = self.topology.p_cores
                        action = 1
                    elif condition == "static_e":
                        target_cores = self.topology.e_cores
                        action = 0
                    elif condition == "round_robin":
                        rr_toggle = 1 - rr_toggle
                        target_cores = self.topology.p_cores if rr_toggle == 1 else self.topology.e_cores
                        action = rr_toggle
                    elif condition == "heuristic":
                        # Rule-based: heavy CPU (> 40%) gets P-cores
                        if proc_stat.cpu_percent > 40.0:
                            target_cores = self.topology.p_cores
                            action = 1
                        else:
                            target_cores = self.topology.e_cores
                            action = 0
                    elif condition == "linucb":
                        action, score = bandit.select_action(context)
                        target_cores = self.topology.p_cores if action == 1 else self.topology.e_cores
                    elif condition == "thompson_sampling":
                        action, score = ts_bandit.select_action(context)
                        target_cores = self.topology.p_cores if action == 1 else self.topology.e_cores

                    supervisor.affinity_controller.set_affinity(managed, target_cores)

                    # Online feedback calculation
                    reward_comps = self.reward_calculator.compute(
                        action=action,
                        invol_ctx_rate=proc_stat.cpu_percent * 5.0,
                    )
                    reward = reward_comps.total_reward

                    if condition == "linucb":
                        bandit.update(action, context, reward)
                    elif condition == "thompson_sampling":
                        ts_bandit.update(action, context, reward)

                    decisions.append({
                        "timestamp": time.time(),
                        "pid": managed.pid,
                        "condition": condition,
                        "action": action,
                        "reward": reward,
                    })

                time.sleep(cycle_interval_seconds)

        finally:
            supervisor.terminate_all()

        avg_cpu = float(np.mean(cpu_samples)) if cpu_samples else 0.0
        avg_power = float(np.mean(power_samples)) if power_samples else 0.0
        avg_fairness = float(np.mean(fairness_samples)) if fairness_samples else 1.0
        elapsed = time.time() - start_time
        edp = avg_power * (elapsed ** 2)

        return TrialResult(
            condition=condition,
            trial_index=trial_index,
            duration_seconds=elapsed,
            total_decisions=len(decisions),
            average_cpu_percent=round(avg_cpu, 2),
            average_power_watts=round(avg_power, 2),
            jain_fairness_index=round(avg_fairness, 4),
            energy_delay_product=round(edp, 2),
            decisions=decisions,
        )
