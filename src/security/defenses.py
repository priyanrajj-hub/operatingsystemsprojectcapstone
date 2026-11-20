"""
Security defenses and mitigations against adversarial manipulation of online bandit schedulers.

Implements:
  1. RobustScaler: Median / Median Absolute Deviation (MAD) feature scaling.
  2. RewardWinsorizer: Clamps extreme outlier rewards to prevent model poisoning.
  3. MahalanobisAnomalyDetector: Detects anomalous feature distributions.
  4. PerPidRateLimiter: Caps bandit update frequency per process ID.
"""

from __future__ import annotations

import logging
import math
import time

import numpy as np

logger = logging.getLogger("aidax.security.defenses")


class RobustScaler:
    """Standardizes features using median and Median Absolute Deviation (MAD)."""

    def __init__(self, eps: float = 1e-4) -> None:
        self.eps = eps
        self.median: np.ndarray | None = None
        self.mad: np.ndarray | None = None

    def fit(self, x: np.ndarray) -> None:
        """Fit median and MAD from a baseline batch."""
        x = np.asarray(x, dtype=float)
        self.median = np.median(x, axis=0)
        deviations = np.abs(x - self.median)
        self.mad = np.median(deviations, axis=0)

    def transform(self, x: np.ndarray) -> np.ndarray:
        """Transform vector x using fitted median and MAD."""
        x = np.asarray(x, dtype=float)
        if self.median is None or self.mad is None:
            return x
        scale = np.where(self.mad > self.eps, self.mad, 1.0)
        return (x - self.median) / scale


class RewardWinsorizer:
    """Clamps extreme scalar reward outliers at fixed percentile thresholds."""

    def __init__(self, min_val: float = -2.0, max_val: float = 2.0) -> None:
        self.min_val = min_val
        self.max_val = max_val

    def winsorize(self, reward: float) -> float:
        """Clamp reward to [min_val, max_val]."""
        if not math.isfinite(reward):
            return self.min_val
        return max(self.min_val, min(self.max_val, reward))


class MahalanobisAnomalyDetector:
    """Detects statistical feature anomalies using Mahalanobis distance."""

    def __init__(self, dim: int = 4, threshold: float = 3.5) -> None:
        self.dim = dim
        self.threshold = threshold
        self.mean = np.zeros(dim, dtype=float)
        self.cov_inv = np.eye(dim, dtype=float)
        self._fitted = False

    def fit(self, samples: np.ndarray) -> None:
        """Fit empirical mean and inverted regularized covariance matrix."""
        samples = np.asarray(samples, dtype=float)
        if len(samples) < self.dim + 2:
            return
        self.mean = np.mean(samples, axis=0)
        cov = np.cov(samples, rowvar=False) + np.eye(self.dim) * 1e-3
        try:
            self.cov_inv = np.linalg.pinv(cov)
            self._fitted = True
        except Exception:
            self._fitted = False

    def is_anomalous(self, x: np.ndarray) -> tuple[bool, float]:
        """Compute Mahalanobis distance D_M(x) and test against threshold."""
        if not self._fitted:
            return False, 0.0
        x = np.asarray(x, dtype=float)
        diff = x - self.mean
        dist_sq = float(diff @ self.cov_inv @ diff)
        dist = math.sqrt(max(0.0, dist_sq))
        return dist > self.threshold, dist


class PerPidRateLimiter:
    """Rate limits bandit parameter updates per PID to prevent rapid adversarial poisoning."""

    def __init__(self, min_interval_seconds: float = 0.2) -> None:
        self.min_interval = min_interval_seconds
        self._last_update: dict[int, float] = {}

    def allow_update(self, pid: int) -> bool:
        """Check whether PID update is allowed under rate limits."""
        now = time.time()
        last = self._last_update.get(pid, 0.0)
        if now - last < self.min_interval:
            return False
        self._last_update[pid] = now
        return True
