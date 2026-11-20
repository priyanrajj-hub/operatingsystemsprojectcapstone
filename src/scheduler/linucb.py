"""
Numerically stable LinUCB Contextual Bandit implementation.
Uses Cholesky factorization and regularized linear solves to prevent matrix inversion instabilities.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import scipy.linalg

logger = logging.getLogger("aidax.scheduler.linucb")


class StableLinUCBArm:
    """
    LinUCB arm with ridge regularization and numerically stable linear solves.

    Maintains:
      A     — (d x d) design matrix regularized by ridge_lambda * I
      b     — (d,) reward accumulator
      theta — Parameter vector computed via Cholesky linear solve A theta = b
    """

    def __init__(self, d: int, exploration_alpha: float = 1.5, ridge_lambda: float = 1.0) -> None:
        self.d = d
        self.exploration_alpha = exploration_alpha
        self.ridge_lambda = ridge_lambda

        self.A = np.eye(d, dtype=float) * ridge_lambda
        self.b = np.zeros(d, dtype=float)
        self.theta = np.zeros(d, dtype=float)
        self._dirty = False

    def _solve_theta(self) -> None:
        """Solve A theta = b using Cholesky factorization for numerical stability."""
        if self._dirty:
            try:
                # Cholesky factor A = L L^T (A is guaranteed symmetric positive-definite due to ridge)
                c, lower = scipy.linalg.cho_factor(self.A, lower=True)
                self.theta = scipy.linalg.cho_solve((c, lower), self.b)
            except (scipy.linalg.LinAlgError, np.linalg.LinAlgError):
                # Fallback to standard regularized least squares solve if ill-conditioned
                self.theta = np.linalg.solve(self.A + np.eye(self.d) * 1e-4, self.b)
            self._dirty = False

    def get_ucb_score(self, x: np.ndarray) -> float:
        """
        Compute Upper Confidence Bound score:
        score = x^T theta + alpha * sqrt(x^T A^{-1} x)
        """
        self._solve_theta()
        x = np.asarray(x, dtype=float)

        # Expected reward: x^T theta
        expected_reward = float(np.dot(x, self.theta))

        # Variance term: x^T A^{-1} x solved stably via A y = x => x^T y
        try:
            c, lower = scipy.linalg.cho_factor(self.A, lower=True)
            y = scipy.linalg.cho_solve((c, lower), x)
            variance = float(np.dot(x, y))
        except Exception:
            inv_A = np.linalg.pinv(self.A)
            variance = float(x @ inv_A @ x)

        uncertainty = math.sqrt(max(0.0, variance))
        return expected_reward + self.exploration_alpha * uncertainty

    def update(self, x: np.ndarray, reward: float) -> None:
        """Online rank-1 parameter update: A <- A + x x^T, b <- b + r x."""
        x = np.asarray(x, dtype=float)
        if not np.all(np.isfinite(x)) or not math.isfinite(reward):
            logger.warning("Rejecting update with non-finite values in context or reward.")
            return

        self.A += np.outer(x, x)
        self.b += reward * x
        self._dirty = True


class StableLinUCBBandit:
    """Multi-armed contextual bandit managing discrete routing actions."""

    def __init__(self, context_dim: int, exploration_alpha: float = 1.5, num_arms: int = 2) -> None:
        self.context_dim = context_dim
        self.exploration_alpha = exploration_alpha
        self.num_arms = num_arms
        self.arms = [StableLinUCBArm(context_dim, exploration_alpha=exploration_alpha) for _ in range(num_arms)]
        self.total_decisions = 0

    def select_action(self, context: np.ndarray) -> tuple[int, float]:
        """Select arm with maximum Upper Confidence Bound score."""
        scores = [arm.get_ucb_score(context) for arm in self.arms]
        best_action = int(np.argmax(scores))
        return best_action, scores[best_action]

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        """Update selected arm parameters."""
        if 0 <= action < self.num_arms:
            self.arms[action].update(context, reward)
            self.total_decisions += 1

    def get_params_snapshot(self) -> dict[str, Any]:
        """Snapshot internal weights for telemetry and persistence."""
        for arm in self.arms:
            arm._solve_theta()
        return {
            "total_decisions": self.total_decisions,
            "arms": [{"theta": arm.theta.tolist(), "exploration_alpha": arm.exploration_alpha} for arm in self.arms],
        }
