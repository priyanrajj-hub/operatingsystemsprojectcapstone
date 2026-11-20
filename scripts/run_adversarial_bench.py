#!/usr/bin/env python3
"""
Adversarial Robustness and Mitigation Benchmark.

Evaluates victim process performance degradation under:
  1. Benign normal baseline
  2. Under attack (local adversarial process manipulating observable telemetry features) without defense
  3. Under attack with active security mitigations (Mahalanobis anomaly detection, Winsorization, rate-limiting)

Reports:
  - Detector True Positive Rate (TPR) on attacker features
  - Detector False Positive Rate (FPR) on benign features
  - Victim optimal core allocation ratios with 95% confidence intervals
  - Real degradation and recovery percentages
  - Defense latency overhead
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from experiments.simulator import BanditGroundTruthEnvironment
from scheduler.linucb import StableLinUCBBandit
from security.defenses import (
    MahalanobisAnomalyDetector,
    PerPidRateLimiter,
    RewardWinsorizer,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.adversarial_bench")


def compute_ci95(data: list[float] | np.ndarray) -> tuple[float, float]:
    """Compute 95% confidence interval half-width and [lower, upper] bounds."""
    arr = np.asarray(data, dtype=float)
    if len(arr) < 2:
        val = float(arr[0]) if len(arr) == 1 else 0.0
        return val, val
    mean = float(np.mean(arr))
    stderr = float(np.std(arr, ddof=1) / np.sqrt(len(arr)))
    h = 1.96 * stderr
    return round(mean - h, 4), round(mean + h, 4)


def run_single_adversarial_trial(
    seed: int,
    n_steps: int = 200,
    detector: MahalanobisAnomalyDetector | None = None,
) -> dict[str, Any]:
    """Execute a single trial evaluating clean, attacked, and defended bandit performance."""
    rng = np.random.default_rng(seed)
    env = BanditGroundTruthEnvironment(context_dim=4, num_arms=3, seed=seed)

    clean_bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=0.5, num_arms=3, seed=seed)
    unprot_bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=0.5, num_arms=3, seed=seed)
    prot_bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=0.5, num_arms=3, seed=seed)

    winsorizer = RewardWinsorizer(min_val=-1.5, max_val=1.5)
    rate_limiter = PerPidRateLimiter(min_interval_seconds=0.01)

    victim_optimal_clean: list[int] = []
    victim_optimal_unprot: list[int] = []
    victim_optimal_prot: list[int] = []

    anomalies_detected = 0
    updates_throttled = 0
    defense_times_us: list[float] = []

    victim_pid = 1001
    attacker_pid = 9999

    for _step in range(n_steps):
        # 1. Benign compute-intensive victim arrives
        # Feature profile: high CPU [0.65, 0.95], moderate mem [0.2, 0.4], thread [0.2, 0.3], bursty 0.0
        victim_ctx = np.array(
            [
                rng.uniform(0.65, 0.95),
                rng.uniform(0.20, 0.40),
                rng.uniform(0.20, 0.30),
                0.0,
            ],
            dtype=float,
        )

        # Baseline Clean
        act_clean, _ = clean_bandit.select_action(victim_ctx, pid=victim_pid)
        r_clean, _, opt_action = env.evaluate_step(victim_ctx, act_clean)
        clean_bandit.update(act_clean, victim_ctx, r_clean, pid=victim_pid)
        victim_optimal_clean.append(1 if act_clean == opt_action else 0)

        # 2. Local Adversary Process
        # Generates observable telemetry feature anomalies (e.g. extreme context switch / duty cycle pulsing)
        # Context switch inflator / extreme outlier pattern
        adv_strategy = rng.choice(["inflator", "duty_spoofer", "feature_mimic"])
        if adv_strategy == "inflator":
            adv_ctx = np.array(
                [
                    rng.uniform(0.05, 0.15),
                    rng.uniform(0.10, 0.20),
                    rng.uniform(5.0, 10.0),  # Extreme involuntary/voluntary switch outlier
                    0.0,
                ],
                dtype=float,
            )
            # Stalling / erratic reward
            adv_reward = -2.5
        elif adv_strategy == "duty_spoofer":
            adv_ctx = np.array(
                [
                    rng.uniform(0.90, 1.0),
                    rng.uniform(0.05, 0.10),
                    rng.uniform(0.10, 0.20),
                    1.0,
                ],
                dtype=float,
            )
            adv_reward = -1.8
        else:
            adv_ctx = np.array(
                [
                    rng.uniform(0.40, 0.60),
                    rng.uniform(0.70, 0.90),
                    rng.uniform(2.0, 4.0),
                    1.0,
                ],
                dtype=float,
            )
            adv_reward = -2.0

        # Unprotected stream: Attacker updates shared bandit
        act_adv_unprot, _ = unprot_bandit.select_action(adv_ctx, pid=attacker_pid)
        unprot_bandit.update(act_adv_unprot, adv_ctx, adv_reward, pid=attacker_pid)

        # Victim scheduled in unprotected bandit
        act_unprot, _ = unprot_bandit.select_action(victim_ctx, pid=victim_pid)
        r_unprot, _, _ = env.evaluate_step(victim_ctx, act_unprot)
        unprot_bandit.update(act_unprot, victim_ctx, r_unprot, pid=victim_pid)
        victim_optimal_unprot.append(1 if act_unprot == opt_action else 0)

        # Protected stream: Security defenses active
        t_def_start = time.perf_counter()
        is_anom, _ = (False, 0.0) if detector is None else detector.is_anomalous(adv_ctx)
        allowed = rate_limiter.allow_update(attacker_pid)
        t_def_end = time.perf_counter()
        defense_times_us.append((t_def_end - t_def_start) * 1e6)

        act_adv_prot, _ = prot_bandit.select_action(adv_ctx, pid=attacker_pid)
        if is_anom:
            anomalies_detected += 1
            # Dropped from updating shared policy
        elif not allowed:
            updates_throttled += 1
        else:
            clipped_r = winsorizer.winsorize(adv_reward)
            prot_bandit.update(act_adv_prot, adv_ctx, clipped_r, pid=attacker_pid)

        # Victim scheduled in protected bandit
        act_prot, _ = prot_bandit.select_action(victim_ctx, pid=victim_pid)
        r_prot, _, _ = env.evaluate_step(victim_ctx, act_prot)
        prot_bandit.update(act_prot, victim_ctx, r_prot, pid=victim_pid)
        victim_optimal_prot.append(1 if act_prot == opt_action else 0)

    # Calculate optimal action ratios over the second half of the trial (after initial learning)
    eval_slice = slice(n_steps // 2, n_steps)
    clean_ratio = float(np.mean(victim_optimal_clean[eval_slice]))
    unprot_ratio = float(np.mean(victim_optimal_unprot[eval_slice]))
    prot_ratio = float(np.mean(victim_optimal_prot[eval_slice]))

    return {
        "clean_ratio": clean_ratio,
        "unprot_ratio": unprot_ratio,
        "prot_ratio": prot_ratio,
        "anomalies_detected": anomalies_detected,
        "updates_throttled": updates_throttled,
        "mean_defense_latency_us": float(np.mean(defense_times_us)),
    }


def evaluate_adversarial_impact(
    n_seeds: int = 15,
    n_steps: int = 200,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute multi-seed adversarial benchmark and report honest metrics."""
    logger.info(
        "Starting adversarial robustness benchmark (%d seeds, %d steps)...",
        n_seeds,
        n_steps,
    )

    rng = np.random.default_rng(42)

    # 1. Fit Mahalanobis Anomaly Detector on baseline benign samples
    benign_train = [
        np.array([rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.5), rng.uniform(0.1, 0.5), 0.0])
        for _ in range(100)
    ]
    detector = MahalanobisAnomalyDetector(dim=4, threshold=3.5)
    detector.fit(np.array(benign_train))

    # 2. Evaluate Detector TPR and FPR
    benign_test = [
        np.array([rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.5), rng.uniform(0.1, 0.5), 0.0])
        for _ in range(200)
    ]
    attacker_test = [
        np.array([rng.uniform(0.05, 0.15), rng.uniform(0.1, 0.2), rng.uniform(5.0, 10.0), 0.0])
        for _ in range(200)
    ]

    benign_flags = sum(1 for x in benign_test if detector.is_anomalous(x)[0])
    attacker_flags = sum(1 for x in attacker_test if detector.is_anomalous(x)[0])

    fpr = round(benign_flags / len(benign_test), 4)
    tpr = round(attacker_flags / len(attacker_test), 4)
    logger.info("Detector Evaluation: TPR=%.4f, FPR=%.4f", tpr, fpr)

    # 3. Multi-seed trial execution
    clean_ratios: list[float] = []
    unprot_ratios: list[float] = []
    prot_ratios: list[float] = []
    defense_latencies: list[float] = []

    for seed_idx in range(n_seeds):
        seed = 500 + seed_idx * 13
        res = run_single_adversarial_trial(seed=seed, n_steps=n_steps, detector=detector)
        clean_ratios.append(res["clean_ratio"])
        unprot_ratios.append(res["unprot_ratio"])
        prot_ratios.append(res["prot_ratio"])
        defense_latencies.append(res["mean_defense_latency_us"])

    mean_clean = float(np.mean(clean_ratios))
    mean_unprot = float(np.mean(unprot_ratios))
    mean_prot = float(np.mean(prot_ratios))

    ci_clean = compute_ci95(clean_ratios)
    ci_unprot = compute_ci95(unprot_ratios)
    ci_prot = compute_ci95(prot_ratios)

    # Honest degradation & recovery calculation
    if mean_clean > 0.0:
        degradation_pct = round(max(0.0, (mean_clean - mean_unprot) / mean_clean * 100.0), 2)
    else:
        degradation_pct = 0.0

    if (mean_clean - mean_unprot) > 1e-4:
        recovery_pct = round(
            min(100.0, max(0.0, (mean_prot - mean_unprot) / (mean_clean - mean_unprot) * 100.0)), 2
        )
    else:
        recovery_pct = 100.0 if mean_prot >= mean_clean else 0.0

    mean_defense_us = round(float(np.mean(defense_latencies)), 2)

    results: dict[str, Any] = {
        "n_seeds": n_seeds,
        "n_steps": n_steps,
        "detector_evaluation": {
            "true_positive_rate": tpr,
            "false_positive_rate": fpr,
            "threshold": detector.threshold,
        },
        "clean_baseline": {
            "mean_optimal_allocation_ratio": round(mean_clean, 4),
            "ci_95": list(ci_clean),
        },
        "attacked_without_defense": {
            "mean_optimal_allocation_ratio": round(mean_unprot, 4),
            "ci_95": list(ci_unprot),
            "allocation_degradation_pct": degradation_pct,
        },
        "attacked_with_defense": {
            "mean_optimal_allocation_ratio": round(mean_prot, 4),
            "ci_95": list(ci_prot),
            "recovery_pct": recovery_pct,
            "mean_defense_latency_us": mean_defense_us,
        },
    }

    if output_path is None:
        output_path = Path("data/processed/adversarial_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("Adversarial benchmark completed. Saved to %s", output_path)
    return results


def main() -> None:
    results = evaluate_adversarial_impact(n_seeds=15, n_steps=200)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
