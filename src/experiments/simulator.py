"""
Contextual Bandit Ground-Truth Environment Simulator.

Evaluates LinUCB and Thompson Sampling regret, parameter convergence,
and learning bounds against known linear payoff functions with sublinear regret verification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from scheduler.linucb import StableLinUCBBandit
from scheduler.thompson_sampling import LinTSBandit

logger = logging.getLogger("aidax.experiments.simulator")


@dataclass
class SimulationResults:
    """Outcome metrics of a multi-epoch bandit simulation."""

    algorithm: str
    n_steps: int
    n_seeds: int
    mean_cumulative_regret: list[float]
    std_cumulative_regret: list[float]
    final_regret: float
    is_sublinear: bool
    estimated_thetas: list[list[float]]


class BanditGroundTruthEnvironment:
    """Simulated contextual environment with known ground-truth theta parameters."""

    def __init__(
        self,
        context_dim: int = 4,
        num_arms: int = 3,
        noise_std: float = 0.1,
        seed: int = 42,
    ) -> None:
        self.context_dim = context_dim
        self.num_arms = num_arms
        self.noise_std = noise_std
        self.rng = np.random.default_rng(seed)

        # Ground-truth orthogonal theta vectors with distinct arm affinities
        # Arm 0 (E-core preference for memory/low-cpu): [0.2, 0.9, -0.3, 0.1]
        # Arm 1 (P-core preference for high-cpu): [1.0, 0.2, 0.8, -0.5]
        # Arm 2 (Unpinned balanced): [0.5, 0.5, 0.2, 0.2]
        self.true_thetas = np.array(
            [
                [0.2, 0.9, -0.3, 0.1],
                [1.0, 0.2, 0.8, -0.5],
                [0.5, 0.5, 0.2, 0.2],
            ],
            dtype=float,
        )[:, :context_dim]

    def sample_context(self) -> np.ndarray:
        """Sample a synthetic workload context uniformly in [0, 1]^d."""
        return self.rng.random(self.context_dim)

    def evaluate_step(self, context: np.ndarray, chosen_action: int) -> tuple[float, float, int]:
        """
        Evaluate step payoff:
        Returns: (observed_noisy_reward, instantaneous_regret, optimal_action)
        """
        expected_rewards = [
            float(np.dot(context, self.true_thetas[a])) for a in range(self.num_arms)
        ]
        optimal_action = int(np.argmax(expected_rewards))
        max_expected = expected_rewards[optimal_action]
        chosen_expected = expected_rewards[chosen_action]

        instantaneous_regret = max_expected - chosen_expected
        noise = float(self.rng.normal(0.0, self.noise_std))
        observed_reward = chosen_expected + noise

        return observed_reward, instantaneous_regret, optimal_action


def run_simulation(
    algorithm: str = "linucb",
    n_steps: int = 500,
    n_seeds: int = 5,
    context_dim: int = 4,
    num_arms: int = 3,
) -> SimulationResults:
    """Execute multi-seed simulation and evaluate cumulative regret growth."""
    all_cumulative_regrets = np.zeros((n_seeds, n_steps), dtype=float)
    final_thetas: list[list[float]] = []

    for seed_idx in range(n_seeds):
        env = BanditGroundTruthEnvironment(
            context_dim=context_dim,
            num_arms=num_arms,
            seed=100 + seed_idx,
        )

        if algorithm == "linucb":
            learner: Any = StableLinUCBBandit(
                context_dim=context_dim,
                num_arms=num_arms,
                exploration_alpha=0.5,
                seed=200 + seed_idx,
            )
        elif algorithm == "thompson_sampling":
            learner = LinTSBandit(
                context_dim=context_dim,
                num_arms=num_arms,
                v=0.3,
                seed=200 + seed_idx,
            )
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        cum_regret = 0.0
        for step in range(n_steps):
            ctx = env.sample_context()
            action, _ = learner.select_action(ctx)
            reward, inst_regret, _ = env.evaluate_step(ctx, action)
            learner.update(action, ctx, reward)
            cum_regret += inst_regret
            all_cumulative_regrets[seed_idx, step] = cum_regret

        if algorithm == "linucb":
            for arm in learner.arms:
                arm._solve_theta()
            final_thetas = [arm.theta.tolist() for arm in learner.arms]

    mean_regret = np.mean(all_cumulative_regrets, axis=0)
    std_regret = np.std(all_cumulative_regrets, axis=0)

    # Verify sublinear growth: rate of regret increase in second half must be lower than first half
    first_half_rate = (mean_regret[n_steps // 2] - mean_regret[0]) / (n_steps // 2)
    second_half_rate = (mean_regret[-1] - mean_regret[n_steps // 2]) / (n_steps // 2)
    is_sublinear = bool(second_half_rate < first_half_rate)

    return SimulationResults(
        algorithm=algorithm,
        n_steps=n_steps,
        n_seeds=n_seeds,
        mean_cumulative_regret=[round(float(r), 4) for r in mean_regret],
        std_cumulative_regret=[round(float(s), 4) for s in std_regret],
        final_regret=round(float(mean_regret[-1]), 4),
        is_sublinear=is_sublinear,
        estimated_thetas=final_thetas,
    )
