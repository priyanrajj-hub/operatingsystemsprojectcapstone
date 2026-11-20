"""
Multi-objective reward formulations with explicit separation of measured, estimated, and simulated energy.

Addresses Research Problem 1:
Eliminates action-dependent circular rewards (1.0 vs 0.3 constants).
Provides:
  - R_perf: Based on measured progress, throughput, and relative latency slowdown.
  - R_energy_measured: System-level energy per completed work from Intel RAPL package deltas.
  - R_legacy: Retained strictly as an ablation baseline to demonstrate the circularity problem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class RewardMode(str, Enum):
    """Evaluation reward mode configuration."""

    PERF = "R_perf"
    ENERGY_MEASURED = "R_energy_measured"
    LEGACY = "R_legacy"


class EnergyMode(str, Enum):
    """Energy calculation provenance."""

    MEASURED_RAPL = "measured_rapl"
    ESTIMATED_HARDWARE = "estimated_hardware"
    SIMULATED_PROXY = "simulated_proxy"


@dataclass
class RewardComponents:
    """Individual decomposed reward terms for transparent telemetry and logging."""

    reward_mode: RewardMode
    progress_term: float
    latency_penalty: float
    energy_penalty: float
    migration_penalty: float
    total_reward: float
    energy_mode: EnergyMode
    details: dict[str, Any]


class RewardCalculator:
    """Configurable reward calculator with strictly non-circular reward formulations."""

    def __init__(
        self,
        reward_mode: RewardMode = RewardMode.PERF,
        alpha_progress: float = 1.0,
        beta_latency: float = 0.5,
        gamma_energy: float = 0.5,
        migration_penalty: float = 0.05,
        energy_mode: EnergyMode = EnergyMode.MEASURED_RAPL,
    ) -> None:
        self.reward_mode = reward_mode
        self.alpha_progress = alpha_progress
        self.beta_latency = beta_latency
        self.gamma_energy = gamma_energy
        self.migration_penalty = migration_penalty
        self.energy_mode = energy_mode

    def compute_perf_reward(
        self,
        progress_work_units: float,
        window_duration_seconds: float,
        latency_ms: float = 0.0,
        baseline_latency_ms: float = 0.0,
        migrated: bool = False,
    ) -> RewardComponents:
        """
        R_perf: Reward driven solely by measured work progress and relative latency.
        No action-dependent constants: P-core, E-core, and unpinned actions compete
        purely on delivered throughput per second and latency.
        """
        duration = max(1e-4, window_duration_seconds)
        throughput = max(0.0, progress_work_units) / duration

        # Progress term: normalized throughput
        progress_term = self.alpha_progress * min(throughput / 100.0, 2.0)

        # Slowdown penalty relative to process's unpinned baseline
        latency_penalty = 0.0
        if baseline_latency_ms > 0.0 and latency_ms > baseline_latency_ms:
            slowdown = (latency_ms - baseline_latency_ms) / baseline_latency_ms
            latency_penalty = self.beta_latency * min(slowdown, 2.0)

        mig_penalty = self.migration_penalty if migrated else 0.0

        total = progress_term - latency_penalty - mig_penalty
        if not math.isfinite(total):
            total = 0.0

        return RewardComponents(
            reward_mode=RewardMode.PERF,
            progress_term=round(progress_term, 4),
            latency_penalty=round(latency_penalty, 4),
            energy_penalty=0.0,
            migration_penalty=round(mig_penalty, 4),
            total_reward=round(total, 4),
            energy_mode=self.energy_mode,
            details={"throughput": throughput, "latency_ms": latency_ms},
        )

    def compute_energy_measured_reward(
        self,
        rapl_delta_joules: float,
        progress_work_units: float,
        migrated: bool = False,
    ) -> RewardComponents:
        """
        R_energy_measured: System-level energy per unit of completed work from Intel RAPL package delta.
        RAPL is package-level, shared across all cores on the socket.
        """
        work = max(1.0, progress_work_units)
        # Joules per completed work unit
        energy_per_work = max(0.0, rapl_delta_joules) / work

        # Negative penalty: reward is higher when energy per task is lower
        energy_penalty = self.gamma_energy * min(energy_per_work / 10.0, 5.0)
        mig_penalty = self.migration_penalty if migrated else 0.0

        total = -(energy_penalty + mig_penalty)
        if not math.isfinite(total):
            total = -1.0

        return RewardComponents(
            reward_mode=RewardMode.ENERGY_MEASURED,
            progress_term=0.0,
            latency_penalty=0.0,
            energy_penalty=round(energy_penalty, 4),
            migration_penalty=round(mig_penalty, 4),
            total_reward=round(total, 4),
            energy_mode=EnergyMode.MEASURED_RAPL,
            details={"rapl_delta_joules": rapl_delta_joules, "work_units": work},
        )

    def compute_legacy_reward(
        self,
        action: int,
        invol_ctx_rate: float,
        migrated: bool = False,
    ) -> RewardComponents:
        """
        R_legacy: The old circular reward formula with fixed P=1.0 and E=0.3 energy costs.
        Retained strictly as an ablation baseline to demonstrate the circularity flaw.
        """
        norm_invol = min(max(0.0, invol_ctx_rate) / 1000.0, 1.0)
        ctx_penalty = 0.7 * norm_invol
        # Action-dependent constant: 1.0 for P-core, 0.3 for E-core, 0.8 for unpinned
        cost_map = {0: 0.3, 1: 1.0, 2: 0.8}
        energy_penalty = 0.3 * cost_map.get(action, 0.5)
        mig_penalty = 0.05 if migrated else 0.0

        total = -(ctx_penalty + energy_penalty + mig_penalty)
        return RewardComponents(
            reward_mode=RewardMode.LEGACY,
            progress_term=0.0,
            latency_penalty=round(ctx_penalty, 4),
            energy_penalty=round(energy_penalty, 4),
            migration_penalty=round(mig_penalty, 4),
            total_reward=round(total, 4),
            energy_mode=EnergyMode.SIMULATED_PROXY,
            details={"action": action, "invol_ctx_rate": invol_ctx_rate},
        )

    def compute(
        self,
        action: int,
        invol_ctx_rate: float = 0.0,
        progress_work_units: float = 10.0,
        window_duration_seconds: float = 1.0,
        latency_ms: float = 0.0,
        baseline_latency_ms: float = 0.0,
        rapl_delta_joules: float = 0.0,
        migrated: bool = False,
    ) -> RewardComponents:
        """Dispatch reward computation according to the configured reward_mode."""
        if self.reward_mode == RewardMode.PERF:
            return self.compute_perf_reward(
                progress_work_units=progress_work_units,
                window_duration_seconds=window_duration_seconds,
                latency_ms=latency_ms,
                baseline_latency_ms=baseline_latency_ms,
                migrated=migrated,
            )
        elif self.reward_mode == RewardMode.ENERGY_MEASURED:
            return self.compute_energy_measured_reward(
                rapl_delta_joules=rapl_delta_joules,
                progress_work_units=progress_work_units,
                migrated=migrated,
            )
        else:
            return self.compute_legacy_reward(
                action=action,
                invol_ctx_rate=invol_ctx_rate,
                migrated=migrated,
            )
