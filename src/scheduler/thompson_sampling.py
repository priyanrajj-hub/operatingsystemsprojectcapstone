"""
Contextual Linear Thompson Sampling (LinTS) baseline.
"""

from __future__ import annotations

import logging

import numpy as np
import scipy.linalg

logger = logging.getLogger("aidax.scheduler.thompson_sampling")


class LinTSArm:
    """One arm of Linear Thompson Sampling with Bayesian posterior parameter sampling."""

    def __init__(self, d: int, v: float = 0.5, ridge_lambda: float = 1.0) -> None:
        self.d = d
        self.v = v  # posterior variance multiplier
        self.A = np.eye(d, dtype=float) * ridge_lambda
        self.b = np.zeros(d, dtype=float)
        self.mu = np.zeros(d, dtype=float)
        self._dirty = False

    def _solve_posterior(self) -> tuple[np.ndarray, np.ndarray]:
        """Compute posterior mean mu and Cholesky factor of covariance."""
        c, lower = scipy.linalg.cho_factor(self.A, lower=True)
        self.mu = scipy.linalg.cho_solve((c, lower), self.b)
        A_inv = scipy.linalg.cho_solve((c, lower), np.eye(self.d))
        return self.mu, A_inv

    def sample_score(self, x: np.ndarray, rng: np.random.Generator) -> float:
        """Sample theta from posterior distribution N(mu, v^2 A^{-1}) and score context x."""
        mu, A_inv = self._solve_posterior()
        # Stable multivariate normal sample via Cholesky of covariance
        cov = (self.v**2) * A_inv
        sampled_theta = rng.multivariate_normal(mu, cov)
        return float(np.dot(x, sampled_theta))

    def update(self, x: np.ndarray, reward: float) -> None:
        """Bayesian online update."""
        self.A += np.outer(x, x)
        self.b += reward * x
        self._dirty = True


class LinTSBandit:
    """Two-armed contextual Linear Thompson Sampling policy."""

    def __init__(self, context_dim: int, num_arms: int = 2, v: float = 0.5, seed: int = 42) -> None:
        self.context_dim = context_dim
        self.num_arms = num_arms
        self.rng = np.random.default_rng(seed)
        self.arms = [LinTSArm(context_dim, v=v) for _ in range(num_arms)]
        self.total_decisions = 0

    def select_action(self, context: np.ndarray) -> tuple[int, float]:
        """Sample posterior rewards and return greedy action with respect to samples."""
        scores = [arm.sample_score(context, self.rng) for arm in self.arms]
        best_action = int(np.argmax(scores))
        return best_action, scores[best_action]

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        """Update selected arm posterior."""
        if 0 <= action < self.num_arms:
            self.arms[action].update(context, reward)
            self.total_decisions += 1
