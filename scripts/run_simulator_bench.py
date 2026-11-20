#!/usr/bin/env python3
"""
Executes Ground-Truth Multi-Seed Bandit Simulation.

Compares cumulative regret dynamics of LinUCB versus Thompson Sampling
against known linear payoff parameters over 1000 decision epochs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from experiments.simulator import run_simulation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.run_sim")


def main() -> None:
    logger.info("Executing LinUCB simulation...")
    linucb_res = run_simulation(algorithm="linucb", n_steps=600, n_seeds=10)

    logger.info("Executing Thompson Sampling simulation...")
    ts_res = run_simulation(algorithm="thompson_sampling", n_steps=600, n_seeds=10)

    output = {
        "linucb": {
            "n_steps": linucb_res.n_steps,
            "final_cumulative_regret": linucb_res.final_regret,
            "is_sublinear": linucb_res.is_sublinear,
            "mean_regret_curve": linucb_res.mean_cumulative_regret,
            "std_regret_curve": linucb_res.std_cumulative_regret,
            "recovered_thetas": linucb_res.estimated_thetas,
        },
        "thompson_sampling": {
            "n_steps": ts_res.n_steps,
            "final_cumulative_regret": ts_res.final_regret,
            "is_sublinear": ts_res.is_sublinear,
            "mean_regret_curve": ts_res.mean_cumulative_regret,
            "std_regret_curve": ts_res.std_cumulative_regret,
        },
    }

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sim_regret.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    logger.info(
        "Simulation completed. LinUCB Final Regret: %.2f (Sublinear: %s). TS Final Regret: %.2f. Saved to %s",
        linucb_res.final_regret,
        linucb_res.is_sublinear,
        ts_res.final_regret,
        out_file,
    )


if __name__ == "__main__":
    main()
