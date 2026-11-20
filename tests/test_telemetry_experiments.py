"""
Tests for telemetry collection, statistical analysis, and workload kernels.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.runner import ExperimentRunner
from experiments.statistics import (
    compute_bootstrap_ci,
    compute_cohens_d,
    holm_bonferroni_correction,
    paired_statistical_comparison,
)
from experiments.workloads import (
    bursty_kernel,
    cpu_intensive_kernel,
    io_intensive_kernel,
    memory_intensive_kernel,
)
from hardware.topology import CPUTopology
from telemetry.collector import TelemetryCollector, compute_jain_fairness


def test_jain_fairness_edge_cases() -> None:
    """Test Jain's fairness calculation under boundary conditions."""
    assert compute_jain_fairness([]) == 1.0
    assert compute_jain_fairness([0.0, 0.0, 0.0]) == 1.0
    assert compute_jain_fairness([50.0, 50.0, 50.0, 50.0]) == 1.0

    # Skewed: 100 on one core, 0 on three cores => J = 100^2 / (4 * 100^2) = 0.25
    assert pytest.approx(compute_jain_fairness([100.0, 0.0, 0.0, 0.0]), 1e-4) == 0.25


def test_telemetry_collector_sample_health() -> None:
    """Test non-blocking hardware telemetry sampling."""
    topo = CPUTopology(
        total_logical_cores=4,
        total_physical_cores=4,
        is_heterogeneous=True,
        detection_method="mock",
        confidence=1.0,
        p_cores=[0, 1],
        e_cores=[2, 3],
        cores=[],
    )
    collector = TelemetryCollector(topology=topo, base_idle_power_w=10.0)
    health = collector.sample_system_health(active_managed_count=2)

    assert health.timestamp > 0
    assert 0.0 <= health.total_cpu_percent <= 100.0
    assert 0.0 <= health.memory_percent <= 100.0
    assert health.active_processes_count == 2
    assert health.estimated_power_watts >= 10.0
    assert 0.0 <= health.jain_fairness_index <= 1.0


def test_bootstrap_ci_coverage() -> None:
    """Test bootstrap confidence interval contains sample mean."""
    data = [10.0, 11.0, 9.5, 10.5, 12.0, 8.5, 10.2]
    mean_val = float(np.mean(data))
    ci_lower, ci_upper = compute_bootstrap_ci(data, confidence_level=0.95, n_resamples=500)

    assert ci_lower <= mean_val <= ci_upper
    assert ci_lower < ci_upper


def test_cohens_d_effect_size() -> None:
    """Test Cohen's d computation for identical and separated distributions."""
    g1 = [10.0, 10.0, 10.0, 10.0]
    g2 = [10.0, 10.0, 10.0, 10.0]
    assert compute_cohens_d(g1, g2) == 0.0

    # Substantial difference
    treatment = [5.0, 5.2, 4.8, 5.1]
    baseline = [15.0, 15.2, 14.9, 15.1]
    d = compute_cohens_d(baseline, treatment)
    assert d > 5.0  # Very large positive effect


def test_holm_bonferroni_correction() -> None:
    """Test step-down multiple comparison correction."""
    p_values = [0.001, 0.015, 0.045, 0.200]
    results = holm_bonferroni_correction(p_values, family_alpha=0.05)
    assert len(results) == 4
    # First test: threshold 0.05 / 4 = 0.0125. 0.001 < 0.0125 => Significant
    assert results[0][1] is True
    # Last test: 0.200 > alpha => Not significant
    assert results[3][1] is False


def test_paired_statistical_comparison() -> None:
    """Test comprehensive paired comparison generation."""
    baseline = [100.0, 105.0, 98.0, 102.0, 104.0]
    treatment = [80.0, 82.0, 79.0, 81.0, 83.0]
    summary = paired_statistical_comparison(baseline, treatment)

    assert summary["percent_improvement"] > 15.0
    assert summary["cohens_d"] > 2.0
    assert summary["p_value_ttest"] < 0.01


def test_workload_kernels_short_burst() -> None:
    """Smoke test synthetic workload execution functions."""
    cpu_iters = cpu_intensive_kernel(duration_seconds=0.1, matrix_size=20)
    assert cpu_iters >= 1

    mem_iters = memory_intensive_kernel(duration_seconds=0.1, array_mb=2)
    assert mem_iters >= 1

    io_iters = io_intensive_kernel(duration_seconds=0.1, chunk_kb=4)
    assert io_iters >= 1

    burst_iters = bursty_kernel(duration_seconds=0.1, compute_slice_s=0.02, sleep_slice_s=0.02)
    assert burst_iters >= 1


def test_experiment_runner_unsupported_condition() -> None:
    """Test error handling on invalid experimental condition."""
    topo = CPUTopology(
        total_logical_cores=4,
        total_physical_cores=4,
        is_heterogeneous=False,
        detection_method="mock",
        confidence=1.0,
        p_cores=[0, 1],
        e_cores=[2, 3],
        cores=[],
    )
    runner = ExperimentRunner(topology=topo)
    with pytest.raises(ValueError, match="Unknown condition 'invalid_algo'"):
        runner.run_condition_trial("invalid_algo", duration_seconds=1.0)
