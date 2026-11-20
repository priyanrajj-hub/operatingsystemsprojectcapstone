"""
Multi-objective reward formulations with explicit separation of measured, estimated, and simulated energy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class EnergyMode(str, Enum):
    """Energy calculation provenance."""

    MEASURED_RAPL = "measured_rapl"
    ESTIMATED_HARDWARE = "estimated_hardware"
    SIMULATED_PROXY = "simulated_proxy"


@dataclass
class RewardComponents:
    """Individual decomposed reward terms for transparent telemetry."""

    involuntary_ctx_penalty: float
    energy_penalty: float
    latency_penalty: float
    migration_penalty: float
    total_reward: float
    energy_mode: EnergyMode


class RewardCalculator:
    """
    Configurable multi-objective reward calculator for heterogeneous CPU scheduling.
    Reward R_t = -(alpha * norm_invol_ctx + beta * energy_term + gamma * latency_term)
    """

    def __init__(
        self,
        alpha_ctx: float = 0.7,
        beta_energy: float = 0.3,
        gamma_latency: float = 0.0,
        p_core_cost: float = 1.0,
        e_core_cost: float = 0.3,
        invol_ctx_norm_divisor: float = 1000.0,
        energy_mode: EnergyMode = EnergyMode.SIMULATED_PROXY,
    ) -> None:
        self.alpha_ctx = alpha_ctx
        self.beta_energy = beta_energy
        self.gamma_latency = gamma_latency
        self.p_core_cost = p_core_cost
        self.e_core_cost = e_core_cost
        self.invol_ctx_norm_divisor = invol_ctx_norm_divisor
        self.energy_mode = energy_mode

    def compute(
        self,
        action: int,
        invol_ctx_rate: float,
        latency_ms: float = 0.0,
        migrated: bool = False,
    ) -> RewardComponents:
        """Compute decomposed scalar reward and return validated components."""
        # Normalize involuntary switch rate to [0, 1] range
        norm_invol = min(max(0.0, invol_ctx_rate) / self.invol_ctx_norm_divisor, 1.0)
        ctx_penalty = self.alpha_ctx * norm_invol

        # Energy penalty according to assigned arm
        energy_cost = self.p_core_cost if action == 0 else self.e_core_cost
        energy_penalty = self.beta_energy * energy_cost

        # Latency term (optional, for completion-time sensitive evaluations)
        norm_latency = min(max(0.0, latency_ms) / 5000.0, 1.0)
        latency_penalty = self.gamma_latency * norm_latency

        migration_penalty = 0.05 if migrated else 0.0

        total_reward = -(ctx_penalty + energy_penalty + latency_penalty + migration_penalty)
        if not math.isfinite(total_reward):
            total_reward = -1.0

        return RewardComponents(
            involuntary_ctx_penalty=round(ctx_penalty, 4),
            energy_penalty=round(energy_penalty, 4),
            latency_penalty=round(latency_penalty, 4),
            migration_penalty=round(migration_penalty, 4),
            total_reward=round(total_reward, 4),
            energy_mode=self.energy_mode,
        )
