"""
Unit tests for LinUCB Sherman-Morrison numerics, parameter recovery, and memory pruning.
"""

from __future__ import annotations

import numpy as np

from aidax.scheduler import AIScheduler, LinUCBArm


def test_linucb_sherman_morrison_accuracy() -> None:
    """Verify that Sherman-Morrison rank-1 update matches explicit np.linalg.inv."""
    d = 5
    arm = LinUCBArm(d=d, exploration_alpha=1.0)
    rng = np.random.default_rng(42)

    for _ in range(50):
        x = rng.normal(size=d)
        reward = float(rng.normal(scale=0.5))
        arm.update(x, reward)

        # Exact inverse check
        exact_inv = np.linalg.inv(arm.A)
        np.testing.assert_allclose(arm.A_inv, exact_inv, rtol=1e-8, atol=1e-8)


def test_linucb_parameter_recovery() -> None:
    """Verify LinUCB recovers true theta parameter on synthetic linear data."""
    d = 4
    true_theta = np.array([0.7, -0.4, 0.2, 0.9])
    arm = LinUCBArm(d=d, exploration_alpha=0.5)
    rng = np.random.default_rng(123)

    for _ in range(800):
        x = rng.normal(size=d)
        noise = float(rng.normal(scale=0.02))
        r = float(x @ true_theta + noise)
        arm.update(x, r)

    np.testing.assert_allclose(arm.theta, true_theta, atol=0.1)


def test_dead_pid_memory_pruning() -> None:
    """Verify that scheduler prunes state for processes that have exited."""
    scheduler = AIScheduler()
    scheduler.history[9999] = {"vol": 10, "invol": 5, "time": 100.0, "last_switch_time": 100.0}
    scheduler.pid_decision_count[9999] = 25

    # Active PIDs does not include 9999
    scheduler.prune_dead_pids(active_pids={1001, 1002})

    assert 9999 not in scheduler.history
    assert 9999 not in scheduler.pid_decision_count
