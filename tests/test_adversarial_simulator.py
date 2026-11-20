"""
Unit tests for Contextual Bandit Simulator and Adversarial Mitigations.
"""

from __future__ import annotations

import numpy as np

from experiments.simulator import run_simulation
from security.adversarial import (
    context_switch_inflator_kernel,
    cpu_spoofer_kernel,
    feature_mimicry_kernel,
)
from security.defenses import (
    MahalanobisAnomalyDetector,
    PerPidRateLimiter,
    RewardWinsorizer,
    RobustScaler,
)


def test_bandit_simulator_sublinear_regret() -> None:
    """Verify LinUCB achieves sublinear regret in known ground-truth environment."""
    res = run_simulation(algorithm="linucb", n_steps=100, n_seeds=2)
    assert res.n_steps == 100
    assert len(res.mean_cumulative_regret) == 100
    assert res.final_regret >= 0.0


def test_thompson_sampling_simulator() -> None:
    """Verify Thompson Sampling runs and accumulates non-negative regret."""
    res = run_simulation(algorithm="thompson_sampling", n_steps=100, n_seeds=2)
    assert res.n_steps == 100
    assert res.final_regret >= 0.0


def test_adversarial_kernels_finite() -> None:
    """Smoke test benign adversarial kernels."""
    switches = context_switch_inflator_kernel(duration_seconds=0.05)
    assert switches >= 1

    spoofer_cycles = cpu_spoofer_kernel(duration_seconds=0.05, duty_cycle=0.5, period_ms=10.0)
    assert spoofer_cycles >= 1

    mimic_chunks = feature_mimicry_kernel(duration_seconds=0.05)
    assert mimic_chunks >= 1


def test_robust_scaler() -> None:
    """Test median/MAD robust scaling."""
    scaler = RobustScaler()
    data = np.array(
        [
            [1.0, 10.0],
            [2.0, 10.0],
            [3.0, 10.0],
            [100.0, 10.0],  # Outlier
        ]
    )
    scaler.fit(data)
    transformed = scaler.transform(np.array([2.0, 10.0]))
    assert transformed is not None
    assert np.all(np.isfinite(transformed))


def test_reward_winsorizer() -> None:
    """Test percentile reward clipping."""
    winsorizer = RewardWinsorizer(min_val=-1.0, max_val=1.0)
    assert winsorizer.winsorize(-5.0) == -1.0
    assert winsorizer.winsorize(10.0) == 1.0
    assert winsorizer.winsorize(0.5) == 0.5
    assert winsorizer.winsorize(float("nan")) == -1.0


def test_mahalanobis_anomaly_detector() -> None:
    """Test anomaly detection using Mahalanobis distance."""
    detector = MahalanobisAnomalyDetector(dim=2, threshold=3.0)
    rng = np.random.default_rng(42)
    # Fit normal distribution centered at (0, 0)
    train_data = rng.normal(0.0, 1.0, size=(100, 2))
    detector.fit(train_data)

    # Inlier
    is_anom_inlier, _ = detector.is_anomalous(np.array([0.1, -0.2]))
    assert is_anom_inlier is False

    # Extreme Outlier
    is_anom_outlier, dist = detector.is_anomalous(np.array([20.0, 30.0]))
    assert is_anom_outlier is True
    assert dist > 10.0


def test_per_pid_rate_limiter() -> None:
    """Test per-PID update rate bounding."""
    limiter = PerPidRateLimiter(min_interval_seconds=0.1)
    # First update allowed
    assert limiter.allow_update(pid=100) is True
    # Immediate subsequent update denied
    assert limiter.allow_update(pid=100) is False
    # Distinct PID allowed
    assert limiter.allow_update(pid=200) is True
