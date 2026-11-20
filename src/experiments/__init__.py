"""
Experiment execution harness, statistical analysis, and workload generators.
"""

from experiments.runner import ExperimentRunner, TrialResult
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

__all__ = [
    "ExperimentRunner",
    "TrialResult",
    "bursty_kernel",
    "compute_bootstrap_ci",
    "compute_cohens_d",
    "cpu_intensive_kernel",
    "holm_bonferroni_correction",
    "io_intensive_kernel",
    "memory_intensive_kernel",
    "paired_statistical_comparison",
]
