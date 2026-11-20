"""
AI-DAX Lite: Results Summary & Statistical Analysis
====================================================
Reads results.csv, computes mean ± std dev per condition, runs paired t-tests
(scipy.stats.ttest_rel) between bandit_adaptive and each baseline, and prints
a formatted comparison table suitable for a paper's Results section.

Also computes Jain's Fairness Index summary per condition.
"""

import sys
import csv
import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:
    print("[WARN] scipy not installed. T-test will be skipped. Install with: pip install scipy")
    scipy_stats = None


def load_results(path='results.csv'):
    """Load results.csv into a dict of {condition: [rows]} using the latest runs."""
    conditions = {}
    with open(path, 'r') as f:
        reader = list(csv.DictReader(f))
        
    latest_rows = reader[-20:]  # 5 trials x 4 conditions = 20 last rows
    for row in latest_rows:
        cond = row['condition']
        if cond not in conditions:
            conditions[cond] = []
        conditions[cond].append(row)
    return conditions


def summarise_condition(rows, metric_key):
    """Return (mean, std) for a given metric across trials."""
    vals = []
    for r in rows:
        try:
            vals.append(float(r[metric_key]))
        except (ValueError, KeyError):
            continue
    if not vals:
        return 0.0, 0.0
    return np.mean(vals), np.std(vals, ddof=1)


def paired_ttest(rows_a, rows_b, metric_key):
    """Run paired t-test between two conditions on a given metric."""
    if scipy_stats is None:
        return None, None

    vals_a, vals_b = [], []
    n = min(len(rows_a), len(rows_b))
    for i in range(n):
        try:
            vals_a.append(float(rows_a[i][metric_key]))
            vals_b.append(float(rows_b[i][metric_key]))
        except (ValueError, KeyError):
            continue

    if len(vals_a) < 2:
        return None, None

    t_stat, p_value = scipy_stats.ttest_rel(vals_a, vals_b)
    return t_stat, p_value


def main():
    results_path = sys.argv[1] if len(sys.argv) > 1 else 'results.csv'

    try:
        conditions = load_results(results_path)
    except FileNotFoundError:
        print(f"ERROR: {results_path} not found. Run evaluate.py first.")
        sys.exit(1)

    metrics = [
        ('mean_cpu_pct', 'Mean CPU %'),
        ('mean_invol_ctx_switches', 'Mean Invol. Ctx Switches'),
        ('median_invol_ctx_switches', 'Median Invol. Ctx Switches'),
        ('p95_invol_ctx_switches', 'P95 Invol. Ctx Switches'),
        ('jain_fairness_index', "Jain's Fairness Index"),
        ('heavy_task_completion_time', "Heavy Completion (s)"),
    ]

    print("=" * 80)
    print("  AI-DAX Lite: Comparative Evaluation Results")
    print("=" * 80)

    # -- Summary Table --
    for metric_key, metric_label in metrics:
        print(f"\n{'-' * 60}")
        print(f"  {metric_label}")
        print(f"{'-' * 60}")
        print(f"  {'Condition':<20} {'Mean':>10} {'± Std Dev':>12} {'N trials':>10}")
        print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*10}")

        for cond_name in ['baseline_cfs', 'static_naive', 'heuristic_only', 'bandit_adaptive']:
            if cond_name not in conditions:
                continue
            rows = conditions[cond_name]
            mean, std = summarise_condition(rows, metric_key)
            print(f"  {cond_name:<20} {mean:>10.2f} {f'± {std:.2f}':>12} {len(rows):>10}")

    # -- Paired T-Tests: bandit_adaptive vs each baseline --
    if scipy_stats and 'bandit_adaptive' in conditions:
        print(f"\n{'=' * 80}")
        print("  Paired T-Tests: bandit_adaptive vs. baselines")
        print(f"{'=' * 80}")

        bandit_rows = conditions['bandit_adaptive']
        for baseline in ['baseline_cfs', 'static_naive', 'heuristic_only']:
            if baseline not in conditions:
                continue
            print(f"\n  -- bandit_adaptive vs {baseline} --")
            print(f"  {'Metric':<30} {'t-stat':>10} {'p-value':>10} {'Significant':>12}")
            print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*12}")

            for metric_key, metric_label in metrics:
                t_stat, p_val = paired_ttest(
                    conditions[baseline], bandit_rows, metric_key
                )
                if t_stat is not None:
                    sig = "Yes (p<0.05)" if p_val < 0.05 else "No"
                    print(f"  {metric_label:<30} {t_stat:>10.3f} {p_val:>10.4f} {sig:>12}")
                else:
                    print(f"  {metric_label:<30} {'N/A':>10} {'N/A':>10} {'N/A':>12}")

    # -- Quick Comparison: Bandit improvement over baselines --
    if 'bandit_adaptive' in conditions:
        print(f"\n{'=' * 80}")
        print("  Relative Improvement (bandit_adaptive vs baselines)")
        print(f"{'=' * 80}")

        bandit_rows = conditions['bandit_adaptive']
        for baseline in ['baseline_cfs', 'static_naive', 'heuristic_only']:
            if baseline not in conditions:
                continue
            base_mean, _ = summarise_condition(conditions[baseline], 'mean_invol_ctx_switches')
            band_mean, _ = summarise_condition(bandit_rows, 'mean_invol_ctx_switches')
            if base_mean > 0:
                improvement = ((base_mean - band_mean) / base_mean) * 100
                print(f"  vs {baseline:<20}: {improvement:>+.1f}% involuntary ctx switches")
            else:
                print(f"  vs {baseline:<20}: N/A (baseline = 0)")

    print(f"\n{'=' * 80}")
    print("  Analysis complete. Use these numbers in your paper's Results section.")
    print(f"{'=' * 80}")


if __name__ == '__main__':
    main()
