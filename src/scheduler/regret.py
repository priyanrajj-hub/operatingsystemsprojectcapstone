"""
Regret tracking distinguishing observed reward, counterfactual regret, and best fixed-action benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegretSnapshot:
    """Detailed regret metrics for research analysis."""

    cumulative_reward: float
    best_fixed_action_reward: float
    pseudo_regret: float
    action_counts: dict[int, int]
    best_fixed_action: int


class RegretTracker:
    """Tracks cumulative reward and computes counterfactual benchmark regret."""

    def __init__(self, num_actions: int = 2) -> None:
        self.num_actions = num_actions
        self.cumulative_reward: float = 0.0
        self.action_reward_sums: dict[int, float] = dict.fromkeys(range(num_actions), 0.0)
        self.action_counts: dict[int, int] = dict.fromkeys(range(num_actions), 0)
        self.counterfactual_history: list[float] = []

    def record_decision(
        self, chosen_action: int, observed_reward: float, counterfactual_rewards: dict[int, float]
    ) -> None:
        """
        Record a decision cycle.
        counterfactual_rewards maps action -> reward that would have been obtained in hindsight.
        """
        self.cumulative_reward += observed_reward
        self.action_counts[chosen_action] += 1

        for a, r in counterfactual_rewards.items():
            if a in self.action_reward_sums:
                self.action_reward_sums[a] += r

    def get_snapshot(self) -> RegretSnapshot:
        """Calculate regret relative to the best single fixed action in hindsight."""
        best_fixed_action = max(self.action_reward_sums, key=lambda a: self.action_reward_sums[a])
        best_fixed_reward = self.action_reward_sums[best_fixed_action]
        # Regret R(T) = max_a \sum r_{t, a} - \sum r_{t, a_t}
        pseudo_regret = max(0.0, best_fixed_reward - self.cumulative_reward)

        return RegretSnapshot(
            cumulative_reward=round(self.cumulative_reward, 4),
            best_fixed_action_reward=round(best_fixed_reward, 4),
            pseudo_regret=round(pseudo_regret, 4),
            action_counts=dict(self.action_counts),
            best_fixed_action=best_fixed_action,
        )
