#!/usr/bin/env python3
"""
Pilot Benchmark Evaluation Script.

Executes pilot trials across core scheduling conditions,
calculates held-out primary metrics against native OS CFS baseline,
and outputs statistical summary to inform Phase 4 Gate Decision.
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


def run_pilot(n_trials: int = 5, trial_duration_s: float = 3.0) -> dict[str, Any]:
    """Execute pilot runs across key scheduling policies."""
    topology = get_cpu_topology()
    runner = ExperimentRunner(topology=topology)
    conditions = ["cfs", "static_p", "static_e", "heuristic", "linucb", "thompson_sampling"]

    results_by_condition: dict[str, list[dict[str, Any]]] = {c: [] for c in conditions}

    logger.info(
        "Starting pilot benchmarks (%d trials per condition, duration=%.1fs)...",
        n_trials,
        trial_duration_s,
    )

    for trial_idx in range(n_trials):
        for cond in conditions:
            seed = 1000 + trial_idx * 17
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
                }
            )

    # Summary statistics
    summary: dict[str, Any] = {}
    cfs_edp = [r["edp"] for r in results_by_condition["cfs"]]

    for cond in conditions:
        edps = [r["edp"] for r in results_by_condition[cond]]
        cpus = [r["cpu_percent"] for r in results_by_condition[cond]]
        fairness = [r["fairness"] for r in results_by_condition[cond]]

        comparison_vs_cfs = paired_statistical_comparison(cfs_edp, edps)

        summary[cond] = {
            "mean_cpu_percent": round(float(np.mean(cpus)), 2),
            "mean_power_watts": round(
                float(np.mean([r["power_watts"] for r in results_by_condition[cond]])), 2
            ),
            "mean_fairness": round(float(np.mean(fairness)), 4),
            "mean_edp": round(float(np.mean(edps)), 2),
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
    data = run_pilot(n_trials=5, trial_duration_s=2.5)
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "pilot_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Pilot benchmark complete. Saved to %s", out_file)


if __name__ == "__main__":
    main()
