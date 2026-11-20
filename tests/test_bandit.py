from __future__ import annotations

import numpy as np

from aidax.scheduler import LinUCBArm, LinUCBBandit


def test_linucb_arm_initialization() -> None:
    d = 5
    arm = LinUCBArm(d=d, exploration_alpha=1.5)
    assert arm.d == d
    assert arm.exploration_alpha == 1.5
    assert np.allclose(arm.A, np.eye(d))
    assert np.allclose(arm.b, np.zeros(d))
    assert np.allclose(arm.theta, np.zeros(d))


def test_linucb_arm_update_math() -> None:
    d = 3
    alpha = 1.0
    arm = LinUCBArm(d=d, exploration_alpha=alpha)

    x = np.array([1.0, 2.0, -1.0])
    reward = 0.5
    arm.update(x, reward)

    expected_A = np.eye(d) + np.outer(x, x)
    expected_b = reward * x
    assert np.allclose(arm.A, expected_A)
    assert np.allclose(arm.b, expected_b)

    score = arm.get_ucb_score(x)
    A_inv = np.linalg.inv(expected_A)
    expected_theta = A_inv @ expected_b
    expected_score = float(x @ expected_theta + alpha * np.sqrt(x @ A_inv @ x))
    assert np.isclose(score, expected_score)


def test_linucb_bandit_action_selection_and_update() -> None:
    context_dim = 4
    bandit = LinUCBBandit(context_dim=context_dim, exploration_alpha=1.0)
    assert len(bandit.arms) == 2
    assert bandit.total_decisions == 0

    x = np.array([0.5, 1.0, 0.2, -0.1])
    action, score = bandit.select_action(x)
    assert action in (0, 1)
    assert isinstance(score, float)

    # Reward arm 0 heavily
    for _ in range(5):
        bandit.update(0, x, reward=10.0)
    # Penalize arm 1
    for _ in range(5):
        bandit.update(1, x, reward=-10.0)

    assert bandit.total_decisions == 10
    best_action, _ = bandit.select_action(x)
    assert best_action == 0

    snapshot = bandit.get_params_snapshot()
    assert snapshot["total_decisions"] == 10
    assert len(snapshot["arm_0_theta"]) == context_dim
    assert len(snapshot["arm_1_theta"]) == context_dim
