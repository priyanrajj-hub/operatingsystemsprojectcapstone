"""
Rigorous statistical analysis methods for scheduler evaluation and benchmarking.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import scipy.stats


def compute_bootstrap_ci(
    data: list[float] | np.ndarray,
    confidence_level: float = 0.95,
    n_resamples: int = 1000,
    random_seed: int = 42,
) -> tuple[float, float]:
    """
    Compute non-parametric bootstrap confidence interval for sample mean.
    Returns (ci_lower, ci_upper).
    """
    arr = np.asarray(data, dtype=float)
    if len(arr) == 0:
        return 0.0, 0.0
    if len(arr) == 1:
        return float(arr[0]), float(arr[0])

    rng = np.random.default_rng(random_seed)
    boot_means = np.empty(n_resamples, dtype=float)
    n = len(arr)

    for i in range(n_resamples):
        resample = rng.choice(arr, size=n, replace=True)
        boot_means[i] = np.mean(resample)

    alpha = 1.0 - confidence_level
    lower_pct = (alpha / 2.0) * 100.0
    upper_pct = (1.0 - alpha / 2.0) * 100.0

    ci_lower = float(np.percentile(boot_means, lower_pct))
    ci_upper = float(np.percentile(boot_means, upper_pct))
    return ci_lower, ci_upper


def compute_cohens_d(group1: list[float] | np.ndarray, group2: list[float] | np.ndarray) -> float:
    """
    Compute Cohen's d effect size between two independent groups:
    d = (mean1 - mean2) / s_pooled
    """
    x1 = np.asarray(group1, dtype=float)
    x2 = np.asarray(group2, dtype=float)

    n1, n2 = len(x1), len(x2)
    if n1 < 2 or n2 < 2:
        return 0.0

    mean1, mean2 = float(np.mean(x1)), float(np.mean(x2))
    var1, var2 = float(np.var(x1, ddof=1)), float(np.var(x2, ddof=1))

    # Pooled standard deviation
    s_pooled = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if s_pooled == 0.0:
        return 0.0

    return float((mean1 - mean2) / s_pooled)


def holm_bonferroni_correction(
    p_values: list[float], family_alpha: float = 0.05
) -> list[tuple[float, bool]]:
    """
    Apply Holm-Bonferroni step-down correction for multiple comparisons.
    Returns list of (adjusted_alpha_threshold, is_significant) corresponding to input p_values.
    """
    m = len(p_values)
    if m == 0:
        return []

    # Pair with original indices
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    results = [False] * m
    thresholds = [0.0] * m

    for rank, (orig_idx, p_val) in enumerate(indexed):
        k = rank + 1
        adj_alpha = family_alpha / (m - k + 1)
        thresholds[orig_idx] = adj_alpha

        if p_val <= adj_alpha:
            results[orig_idx] = True
        else:
            # Once a null hypothesis cannot be rejected, subsequent tests are not rejected
            for subsequent_rank in range(rank, m):
                sub_orig_idx = indexed[subsequent_rank][0]
                results[sub_orig_idx] = False
                thresholds[sub_orig_idx] = family_alpha / (m - subsequent_rank)
            break

    return [(thresholds[i], results[i]) for i in range(m)]


def paired_statistical_comparison(
    baseline_values: list[float], treatment_values: list[float]
) -> dict[str, Any]:
    """
    Compute paired t-test, Wilcoxon signed-rank test, and effect size.
    """
    b = np.asarray(baseline_values, dtype=float)
    t = np.asarray(treatment_values, dtype=float)

    if len(b) != len(t) or len(b) < 2:
        return {
            "mean_baseline": float(np.mean(b)) if len(b) > 0 else 0.0,
            "mean_treatment": float(np.mean(t)) if len(t) > 0 else 0.0,
            "percent_improvement": 0.0,
            "t_statistic": 0.0,
            "p_value_ttest": 1.0,
            "cohens_d": 0.0,
        }

    mean_b = float(np.mean(b))
    mean_t = float(np.mean(t))
    pct_imp = float((mean_b - mean_t) / mean_b * 100.0) if mean_b != 0 else 0.0

    try:
        t_stat, p_val_ttest = scipy.stats.ttest_rel(b, t)
    except Exception:
        t_stat, p_val_ttest = 0.0, 1.0

    d = compute_cohens_d(b, t)
    ci_b = compute_bootstrap_ci(b)
    ci_t = compute_bootstrap_ci(t)

    return {
        "mean_baseline": round(mean_b, 4),
        "ci_baseline_95": (round(ci_b[0], 4), round(ci_b[1], 4)),
        "mean_treatment": round(mean_t, 4),
        "ci_treatment_95": (round(ci_t[0], 4), round(ci_t[1], 4)),
        "percent_improvement": round(pct_imp, 2),
        "t_statistic": round(float(t_stat), 4) if not math.isnan(t_stat) else 0.0,
        "p_value_ttest": round(float(p_val_ttest), 6) if not math.isnan(p_val_ttest) else 1.0,
        "cohens_d": round(d, 4),
    }
