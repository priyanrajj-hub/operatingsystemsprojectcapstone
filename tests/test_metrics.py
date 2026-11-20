from __future__ import annotations

import numpy as np

from aidax.evaluate import aggregate_metrics, compute_jain_fairness


def test_jain_fairness_equal_allocation() -> None:
    # When all processes get equal CPU time, fairness must be exactly 1.0
    times = [10.0, 10.0, 10.0, 10.0]
    fairness = compute_jain_fairness(times)
    assert np.isclose(fairness, 1.0)


def test_jain_fairness_unfair_allocation() -> None:
    # If 1 of 4 processes gets all CPU time, fairness is 1/4 = 0.25
    times = [100.0, 0.0, 0.0, 0.0]
    fairness = compute_jain_fairness(times)
    assert np.isclose(fairness, 0.25)


def test_jain_fairness_empty_and_zero() -> None:
    assert compute_jain_fairness([]) == 0.0
    assert compute_jain_fairness([0.0, 0.0]) == 0.0


def test_aggregate_metrics() -> None:
    sample_records = [
        {
            "pid": 1,
            "type": "Heavy",
            "mean_cpu": 80.0,
            "mean_invol_ctx": 10.0,
            "median_invol_ctx": 8.0,
            "p95_invol_ctx": 12.0,
            "total_cpu_time": 100.0,
            "completion_time": 15.0,
        },
        {
            "pid": 2,
            "type": "Light",
            "mean_cpu": 20.0,
            "mean_invol_ctx": 2.0,
            "median_invol_ctx": 2.0,
            "p95_invol_ctx": 4.0,
            "total_cpu_time": 25.0,
            "completion_time": 10.0,
        },
    ]

    agg = aggregate_metrics(sample_records)
    assert np.isclose(agg["mean_cpu"], 50.0)
    assert np.isclose(agg["mean_invol_ctx"], 6.0)
    assert agg["n_processes"] == 2
    assert np.isclose(agg["heavy_task_completion_time"], 15.0)
    assert agg["jain_fairness"] > 0.0
