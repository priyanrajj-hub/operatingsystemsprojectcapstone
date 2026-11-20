from __future__ import annotations

import numpy as np

from scheduler.linucb import SafeWelfordScaler, StableLinUCBBandit


def test_scaler_appends_intercept_and_freezes() -> None:
    """Verify that SafeWelfordScaler appends a 1.0 intercept and freezes after calibration."""
    scaler = SafeWelfordScaler(dim=4, calibration_steps=10)
    rng = np.random.default_rng(42)

    # During calibration
    for _ in range(10):
        x = rng.uniform(1.0, 5.0, size=4)
        scaler.update(x)

    assert scaler.frozen is True

    # Transform must return 5 dimensions (4 scaled + 1.0 intercept)
    test_vec = np.array([2.0, 3.0, 4.0, 5.0])
    transformed = scaler.transform(test_vec)
    assert len(transformed) == 5
    assert transformed[-1] == 1.0


def test_bandit_deterministic_reward_p_core_selection() -> None:
    """
    Reviewer C3 requirement:
    With deterministic rewards (P=1.0, others 0.2),
    the bandit must choose P >= 90% over the last 100 of 200 steps across 20 seeds.
    """
    p_choices = []
    num_seeds = 20

    for seed in range(num_seeds):
        # 4 context features, 3 arms: [0: E-core, 1: P-core, 2: CFS/unpinned]
        bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=0.5, num_arms=3, seed=seed)
        rng = np.random.default_rng(seed)
        chosen_last_100 = 0

        for t in range(200):
            ctx = rng.uniform(0.1, 0.9, size=4)
            action, _ = bandit.select_action(ctx)
            # Arm 1 is P-core with 1.0 reward, others give 0.2
            reward = 1.0 if action == 1 else 0.2
            bandit.update(action, ctx, reward)

            if t >= 100 and action == 1:
                chosen_last_100 += 1

        p_choices.append(chosen_last_100)

    mean_p_rate = np.mean(p_choices)
    print(f"Mean P-core selection in last 100 steps: {mean_p_rate:.1f}%")
    assert mean_p_rate >= 90.0, f"Expected >= 90% P-core selection, got {mean_p_rate}%"


def test_bandit_offset_linear_reward_simulator() -> None:
    """Verify that LinUCB recovers preference under non-zero-mean offset linear reward."""
    bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=0.3, num_arms=2, seed=99)
    rng = np.random.default_rng(99)

    # Arm 0 has base offset 0.2; Arm 1 has base offset 0.8
    beta = np.array([0.1, -0.05, 0.08, 0.02])
    arm1_selected_last_100 = 0

    for t in range(200):
        ctx = rng.uniform(0.0, 1.0, size=4)
        action, _ = bandit.select_action(ctx)
        noise = rng.normal(scale=0.01)
        if action == 1:
            reward = 0.8 + float(np.dot(ctx, beta)) + noise
        else:
            reward = 0.2 + float(np.dot(ctx, beta)) + noise

        bandit.update(action, ctx, reward)
        if t >= 100 and action == 1:
            arm1_selected_last_100 += 1

    assert arm1_selected_last_100 >= 90
