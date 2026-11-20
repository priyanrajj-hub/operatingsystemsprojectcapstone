#!/usr/bin/env python3
"""
Pilot Benchmark Evaluation Script.

Executes pilot trials across key scheduling policies:
  1. CFS (Default OS CFS scheduler, unpinned)
  2. Static P-core (Pinned exclusively to high-performance cores)
  3. Static E-core (Pinned exclusively to energy-efficient cores)
  4. Round-Robin (Per-process round-robin across core partitions)
  5. Epsilon-Greedy (Multi-armed bandit with decaying exploration)
  6. Heuristic (Deterministic rule-based utilization mapping)
  7. LinUCB (Online contextual bandit with ridge regression)
  8. Thompson Sampling (Bayesian contextual bandit)
  9. Oracle Static (Hindsight optimal static assignment per workload class)

Calculates held-out primary metrics against native OS CFS baseline,
and outputs statistical summary with full empirical disclosures.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from experiments.runner import ExperimentRunner
from experiments.statistics import paired_statistical_comparison
from hardware.detection import get_cpu_topology

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.pilot_bench")


def run_pilot(n_trials: int = 3, trial_duration_s: float = 2.5) -> dict[str, Any]:
    """Execute pilot runs across key scheduling policies."""
    topology = get_cpu_topology()
    runner = ExperimentRunner(topology=topology)
    conditions = [
        "cfs",
        "static_p",
        "static_e",
        "round_robin",
        "epsilon_greedy",
        "heuristic",
        "linucb",
        "thompson_sampling",
        "oracle_static",
    ]

    results_by_condition: dict[str, list[dict[str, Any]]] = {c: [] for c in conditions}

    logger.info(
        "Starting pilot benchmarks (%d trials per condition across %d conditions, duration=%.1fs)...",
        n_trials,
        len(conditions),
        trial_duration_s,
    )

    for trial_idx in range(n_trials):
        for cond in conditions:
            seed = 1000 + trial_idx * 17
            logger.info("Running trial %d/%d for condition '%s'...", trial_idx + 1, n_trials, cond)
            res = runner.run_condition_trial(
                condition=cond,
                trial_index=trial_idx,
                duration_seconds=trial_duration_s,
                cycle_interval_seconds=0.2,
                seed=seed,
            )
            results_by_condition[cond].append(
                {
                    "trial": trial_idx,
                    "cpu_percent": res.average_cpu_percent,
                    "power_watts": res.average_power_watts,
                    "fairness": res.jain_fairness_index,
                    "edp": res.energy_delay_product,
                    "decisions": res.total_decisions,
                    "involuntary_ctx_switches": res.total_involuntary_ctx_switches,
                    "energy_mode": res.energy_mode,
                }
            )

    # Summary statistics
    summary: dict[str, Any] = {}
    cfs_edp = [r["edp"] for r in results_by_condition["cfs"]]

    for cond in conditions:
        edps = [r["edp"] for r in results_by_condition[cond]]
        cpus = [r["cpu_percent"] for r in results_by_condition[cond]]
        fairness = [r["fairness"] for r in results_by_condition[cond]]
        decisions_list = [r["decisions"] for r in results_by_condition[cond]]
        invol_ctx_list = [r["involuntary_ctx_switches"] for r in results_by_condition[cond]]

        comparison_vs_cfs = paired_statistical_comparison(cfs_edp, edps)

        summary[cond] = {
            "mean_cpu_percent": round(float(np.mean(cpus)), 2),
            "mean_power_watts": round(
                float(np.mean([r["power_watts"] for r in results_by_condition[cond]])), 2
            ),
            "mean_fairness": round(float(np.mean(fairness)), 4),
            "mean_edp": round(float(np.mean(edps)), 2),
            "mean_decisions": round(float(np.mean(decisions_list)), 1),
            "mean_involuntary_ctx_switches": round(float(np.mean(invol_ctx_list)), 1),
            "edp_comparison_vs_cfs": comparison_vs_cfs,
        }

    return {
        "n_trials": n_trials,
        "trial_duration_s": trial_duration_s,
        "is_simulated": not topology.is_heterogeneous,
        "detection_method": topology.detection_method,
        "summary": summary,
        "raw_trials": results_by_condition,
    }


def main() -> None:
    data = run_pilot(n_trials=3, trial_duration_s=2.5)
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "pilot_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Pilot benchmark complete. Saved to %s", out_file)


if __name__ == "__main__":
    main()
