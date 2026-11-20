"""
Numerically stable LinUCB Contextual Bandit implementation.
Uses Cholesky factorization, Sherman-Morrison rank-1 updates, and regularized linear solves.

Addresses Research Problems 2 & 5:
- 3 Arms: [0: E-core, 1: P-core, 2: Unpinned / Kernel CFS fallback].
- Frozen calibration mode in SafeWelfordScaler to avoid moving-coordinate instabilities.
- Feature clipping and non-finite value rejection.
- Shared vs Per-PID bandit model architectures.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import scipy.linalg

logger = logging.getLogger("aidax.scheduler.linucb")


class SafeWelfordScaler:
    """
    Welford's algorithm with zero-variance safeguards, frozen calibration, and intercept.
    Standardizes raw features to zero-mean unit-variance and appends a constant 1.0
    intercept feature to allow linear models to learn arm baseline offsets.
    """

    def __init__(self, dim: int, calibration_steps: int = 30, eps: float = 1e-4) -> None:
        self.dim = dim
        self.calibration_steps = calibration_steps
        self.eps = eps
        self.count = 0
        self.mean = np.zeros(dim, dtype=float)
        self.M2 = np.zeros(dim, dtype=float)
        self.frozen = False

    def update(self, x: np.ndarray) -> None:
        """Update running mean and variance if not frozen."""
        if self.frozen:
            return
        x = np.asarray(x, dtype=float)[: self.dim]
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.M2 += delta * delta2

        if self.count >= self.calibration_steps:
            self.frozen = True
            logger.info(
                "SafeWelfordScaler completed calibration (%d steps); frozen scaling active.",
                self.count,
            )

    def transform(self, x: np.ndarray) -> np.ndarray:
        """Standardize context: (x - mean) / (std + eps) and append 1.0 intercept."""
        x = np.asarray(x, dtype=float)[: self.dim]
        if self.count < 2:
            z = x
        else:
            variance = self.M2 / (self.count - 1)
            std = np.sqrt(np.maximum(0.0, variance)) + self.eps
            z = (x - self.mean) / std
        return np.append(z, 1.0)


class StableLinUCBArm:
    """
    LinUCB arm with ridge regularization and numerically stable linear solves.

    Maintains:
      A     — (d x d) design matrix regularized by ridge_lambda * I
      b     — (d,) reward accumulator
      theta — Parameter vector computed via Cholesky linear solve A theta = b
    """

    def __init__(self, d: int, exploration_alpha: float = 1.0, ridge_lambda: float = 1.0) -> None:
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
        x = np.clip(x, -10.0, 10.0)

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
        x = np.clip(x, -10.0, 10.0)
        if not np.all(np.isfinite(x)) or not math.isfinite(reward):
            logger.warning("Rejecting update with non-finite values in context or reward.")
            return

        self.A += np.outer(x, x)
        self.b += reward * x
        self._dirty = True


class StableLinUCBBandit:
    """
    Multi-armed contextual bandit managing discrete routing actions.
    Supports 3 arms:
      - Action 0: Efficiency Core (E-core)
      - Action 1: Performance Core (P-core)
      - Action 2: Unpinned / Kernel CFS Fallback

    Features:
      - Intercept-augmented feature representation (dim + 1).
      - Calibration warm-up phase with round-robin exploration.
      - Selection-time scaled context caching for exact update-time reuse.
    """

    def __init__(
        self,
        context_dim: int = 4,
        exploration_alpha: float = 1.0,
        num_arms: int = 3,
        seed: int = 42,
        calibration_steps: int = 30,
    ) -> None:
        self.context_dim = context_dim
        self.exploration_alpha = exploration_alpha
        self.num_arms = num_arms
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.effective_dim = context_dim + 1  # includes appended 1.0 intercept
        self.arms = [
            StableLinUCBArm(self.effective_dim, exploration_alpha=exploration_alpha)
            for _ in range(num_arms)
        ]
        self.scaler = SafeWelfordScaler(dim=context_dim, calibration_steps=calibration_steps)
        self.total_decisions = 0
        self._context_cache: dict[int, np.ndarray] = {}

    def select_action(self, context: np.ndarray, pid: int = 0) -> tuple[int, float]:
        """Select arm with maximum Upper Confidence Bound score."""
        # 1. Warm-up / calibration phase
        if not self.scaler.frozen:
            self.scaler.update(context)
            action = self.scaler.count % self.num_arms
            scaled_ctx = self.scaler.transform(context)
            self._context_cache[pid] = scaled_ctx
            return action, 0.0

        # 2. Exploitation / Exploration LinUCB selection
        scaled_ctx = self.scaler.transform(context)
        self._context_cache[pid] = scaled_ctx
        scores = [arm.get_ucb_score(scaled_ctx) for arm in self.arms]
        best_action = int(np.argmax(scores))
        return best_action, scores[best_action]

    def update(self, action: int, context: np.ndarray, reward: float, pid: int = 0) -> None:
        """Update selected arm parameters reusing exact selection-time scaled context."""
        if 0 <= action < self.num_arms:
            scaled_ctx = self._context_cache.pop(pid, None)
            if scaled_ctx is None:
                scaled_ctx = self.scaler.transform(context)
            self.arms[action].update(scaled_ctx, reward)
            self.total_decisions += 1

    def get_params_snapshot(self) -> dict[str, Any]:
        """Snapshot internal weights for telemetry and persistence."""
        for arm in self.arms:
            arm._solve_theta()
        return {
            "total_decisions": self.total_decisions,
            "num_arms": self.num_arms,
            "arms": [
                {
                    "theta": arm.theta.tolist(),
                    "exploration_alpha": arm.exploration_alpha,
                    "ridge_lambda": arm.ridge_lambda,
                }
                for arm in self.arms
            ],
        }


class PerPidBanditScheduler:
    """Manages dedicated contextual bandit instances per managed workload or PID."""

    def __init__(
        self,
        context_dim: int = 4,
        exploration_alpha: float = 1.0,
        num_arms: int = 3,
        seed: int = 42,
    ) -> None:
        self.context_dim = context_dim
        self.exploration_alpha = exploration_alpha
        self.num_arms = num_arms
        self.seed = seed
        self._bandits: dict[str, StableLinUCBBandit] = {}

    def get_bandit(self, workload_key: str) -> StableLinUCBBandit:
        """Get or initialize a bandit for a specific workload category or PID."""
        if workload_key not in self._bandits:
            self._bandits[workload_key] = StableLinUCBBandit(
                context_dim=self.context_dim,
                exploration_alpha=self.exploration_alpha,
                num_arms=self.num_arms,
                seed=self.seed + len(self._bandits),
            )
        return self._bandits[workload_key]
