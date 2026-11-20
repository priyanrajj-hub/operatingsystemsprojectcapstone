#!/usr/bin/env python3
"""
Adversarial Robustness and Mitigation Benchmark.

Evaluates victim process performance degradation under:
  1. Benign normal baseline
  2. Under attack (context-switch inflation and feature mimicry) without defense
  3. Under attack with active security mitigations (Mahalanobis detection, Winsorization, rate-limiting)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from scheduler.linucb import StableLinUCBBandit
from security.defenses import (
    MahalanobisAnomalyDetector,
    PerPidRateLimiter,
    RewardWinsorizer,
    RobustScaler,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.adversarial_bench")


def evaluate_adversarial_impact(n_steps: int = 200) -> dict[str, Any]:
    """Simulate clean vs attacked vs defended bandit decision streams."""
    rng = np.random.default_rng(42)

    # Clean normal process context: [CPU% 60-80, Mem 200-400, Threads 2-4, Bursty 0]
    # Attacker process context: [Spoofed CPU% 10-20, Normal Mem, Context-switch extreme 900+]
    clean_bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0, num_arms=3, seed=10)
    unprotected_bandit = StableLinUCBBandit(
        context_dim=4, exploration_alpha=1.0, num_arms=3, seed=20
    )
    protected_bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0, num_arms=3, seed=30)

    # Train anomaly detector on 50 clean baseline contexts
    clean_history = [
        np.array([rng.uniform(0.6, 0.8), rng.uniform(0.2, 0.4), 0.25, 0.0]) for _ in range(50)
    ]
    detector = MahalanobisAnomalyDetector(dim=4, threshold=3.0)
    detector.fit(np.array(clean_history))

    robust_scaler = RobustScaler()
    robust_scaler.fit(np.array(clean_history))
    winsorizer = RewardWinsorizer(min_val=-1.5, max_val=1.5)
    rate_limiter = PerPidRateLimiter(min_interval_seconds=0.01)

    victim_actions_clean: list[int] = []
    victim_actions_unprotected: list[int] = []
    victim_actions_protected: list[int] = []

    anomalies_detected = 0
    updates_throttled = 0

    for _step in range(n_steps):
        # 1. Normal victim task arriving
        victim_ctx = np.array(
            [
                rng.uniform(0.65, 0.85),  # heavy compute
                rng.uniform(0.2, 0.35),
                0.25,
                0.0,
            ]
        )

        act_clean, _ = clean_bandit.select_action(victim_ctx)
        clean_bandit.update(act_clean, victim_ctx, reward=1.0 if act_clean == 1 else 0.2)
        victim_actions_clean.append(act_clean)

        # 2. Under attack without defense
        # Adversary injects spoofed poisoned data claiming huge rewards for wrong arm
        adversary_ctx = np.array(
            [
                rng.uniform(0.05, 0.15),  # spoofed low CPU
                rng.uniform(0.1, 0.2),
                0.1,
                1.0,
            ]
        )
        # Adversary poisons model by giving extreme reward (e.g. +10.0) on E-core
        unprotected_bandit.update(action=0, context=adversary_ctx, reward=10.0)

        # Victim makes decision with poisoned model
        act_unprot, _ = unprotected_bandit.select_action(victim_ctx)
        unprotected_bandit.update(act_unprot, victim_ctx, reward=1.0 if act_unprot == 1 else 0.2)
        victim_actions_unprotected.append(act_unprot)

        # 3. Under attack with defense
        is_anom, _ = detector.is_anomalous(adversary_ctx)
        allowed = rate_limiter.allow_update(pid=9999)

        if is_anom:
            anomalies_detected += 1
        elif not allowed:
            updates_throttled += 1
        else:
            winsorized_reward = winsorizer.winsorize(10.0)
            norm_adv_ctx = robust_scaler.transform(adversary_ctx)
            protected_bandit.update(action=0, context=norm_adv_ctx, reward=winsorized_reward)

        act_prot, _ = protected_bandit.select_action(victim_ctx)
        protected_bandit.update(act_prot, victim_ctx, reward=1.0 if act_prot == 1 else 0.2)
        victim_actions_protected.append(act_prot)

    # Ideal allocation for compute-heavy victim is P-core (Action 1)
    clean_p_ratio = float(np.mean([1 if a == 1 else 0 for a in victim_actions_clean]))
    unprot_p_ratio = float(np.mean([1 if a == 1 else 0 for a in victim_actions_unprotected]))
    prot_p_ratio = float(np.mean([1 if a == 1 else 0 for a in victim_actions_protected]))

    results = {
        "n_steps": n_steps,
        "clean_baseline": {
            "optimal_p_core_allocation_ratio": round(clean_p_ratio, 4),
        },
        "attacked_without_defense": {
            "optimal_p_core_allocation_ratio": round(unprot_p_ratio, 4),
            "allocation_degradation_pct": round(
                (clean_p_ratio - unprot_p_ratio) / clean_p_ratio * 100.0, 2
            ),
        },
        "attacked_with_defense": {
            "optimal_p_core_allocation_ratio": round(prot_p_ratio, 4),
            "recovery_pct": round(
                (prot_p_ratio - unprot_p_ratio) / (clean_p_ratio - unprot_p_ratio) * 100.0, 2
            ),
            "anomalies_detected": anomalies_detected,
            "updates_throttled": updates_throttled,
        },
    }

    logger.info(
        "Adversarial Impact: Clean P-Ratio=%.2f, Under Attack=%.2f (Degradation=%.1f%%), Defended=%.2f (Recovery=%.1f%%)",
        clean_p_ratio,
        unprot_p_ratio,
        results["attacked_without_defense"]["allocation_degradation_pct"],
        prot_p_ratio,
        results["attacked_with_defense"]["recovery_pct"],
    )
    return results


def main() -> None:
    res = evaluate_adversarial_impact()
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "adversarial_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    logger.info("Adversarial results saved to %s", out_file)


if __name__ == "__main__":
    main()
