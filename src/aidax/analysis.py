"""
AI-DAX Lite: Results Summary & Statistical Analysis
====================================================
Loads evaluation benchmark outputs (results.csv or log outputs), computes
mean +- std dev per condition, computes Jain's Fairness Index, and conducts
paired Student's t-tests (scipy.stats.ttest_rel) between bandit_adaptive and
the scheduling baselines.

Supports output formats:
- Plaintext terminal report (suitable for console inspection)
- Markdown tables (ready for inclusion in papers and reports)
- JSON (for programmatic ingestion or dashboard metrics)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
from typing import Any

import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None

logger = logging.getLogger("aidax.analysis")

STANDARD_METRICS: list[tuple[str, str]] = [
    ("mean_cpu_pct", "Mean CPU %"),
    ("mean_invol_ctx_switches", "Mean Invol. Ctx Switches"),
    ("median_invol_ctx_switches", "Median Invol. Ctx Switches"),
    ("p95_invol_ctx_switches", "P95 Invol. Ctx Switches"),
    ("jain_fairness_index", "Jain's Fairness Index"),
    ("heavy_task_completion_time", "Heavy Completion (s)"),
]

CONDITION_ORDER: list[str] = [
    "baseline_cfs",
    "static_naive",
    "heuristic_only",
    "bandit_adaptive",
]


def load_results(
    path: str = "results/results.csv",
    tail_n: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Load a results.csv file into a dictionary grouped by condition.
    Optionally limits to the last tail_n rows.
    """
    if not open(path, encoding="utf-8"):
        raise FileNotFoundError(f"{path} not found.")

    conditions: dict[str, list[dict[str, Any]]] = {}
    with open(path, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    target_rows = reader if tail_n is None else reader[-tail_n:]
    for row in target_rows:
        cond = row.get("condition", "unknown")
        if cond not in conditions:
            conditions[cond] = []
        conditions[cond].append(row)

    return conditions


def summarise_condition(
    rows: list[dict[str, Any]],
    metric_key: str,
) -> tuple[float, float]:
    """Compute (mean, sample_std_dev) for a metric across condition trials."""
    vals: list[float] = []
    for r in rows:
        try:
            val = float(r[metric_key])
            vals.append(val)
        except (ValueError, KeyError, TypeError):
            continue

    if not vals:
        return 0.0, 0.0
    if len(vals) == 1:
        return float(vals[0]), 0.0
    return float(np.mean(vals)), float(np.std(vals, ddof=1))


def paired_ttest(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    metric_key: str,
) -> tuple[float | None, float | None]:
    """
    Conduct a paired Student's t-test between two condition trial sets.
    Returns (t_statistic, p_value), or (None, None) if unavailable.
    """
    if scipy_stats is None:
        return None, None

    vals_a: list[float] = []
    vals_b: list[float] = []
    n = min(len(rows_a), len(rows_b))

    for i in range(n):
        try:
            vals_a.append(float(rows_a[i][metric_key]))
            vals_b.append(float(rows_b[i][metric_key]))
        except (ValueError, KeyError, TypeError):
            continue

    if len(vals_a) < 2:
        return None, None

    # If differences are all zero, t is 0 and p is 1.0
    diff = np.array(vals_a) - np.array(vals_b)
    if np.all(diff == 0):
        return 0.0, 1.0

    res = scipy_stats.ttest_rel(vals_a, vals_b)
    return float(res.statistic), float(res.pvalue)


def compute_relative_improvements(
    conditions: dict[str, list[dict[str, Any]]],
    metric_key: str = "mean_invol_ctx_switches",
) -> dict[str, float | None]:
    """
    Compute percentage improvement of bandit_adaptive over each baseline.
    Positive percentage implies reduction / improvement in overhead.
    """
    improvements: dict[str, float | None] = {}
    if "bandit_adaptive" not in conditions:
        return improvements

    bandit_mean, _ = summarise_condition(conditions["bandit_adaptive"], metric_key)

    for baseline in ["baseline_cfs", "static_naive", "heuristic_only"]:
        if baseline not in conditions:
            continue
        base_mean, _ = summarise_condition(conditions[baseline], metric_key)
        if base_mean > 0:
            pct = ((base_mean - bandit_mean) / base_mean) * 100.0
            improvements[baseline] = round(pct, 2)
        else:
            improvements[baseline] = None

    return improvements


def format_text_report(
    conditions: dict[str, list[dict[str, Any]]],
    metrics: list[tuple[str, str]] | None = None,
) -> str:
    """Format full comparative statistical analysis as formatted text."""
    if metrics is None:
        metrics = STANDARD_METRICS

    lines: list[str] = [
        "=" * 80,
        "  AI-DAX Lite: Comparative Evaluation Results",
        "=" * 80,
    ]

    for metric_key, metric_label in metrics:
        lines.append(f"\n{'-' * 60}")
        lines.append(f"  {metric_label}")
        lines.append(f"{'-' * 60}")
        lines.append(f"  {'Condition':<20} {'Mean':>10} {'+- Std Dev':>12} {'N trials':>10}")
        lines.append(f"  {'-' * 20} {'-' * 10} {'-' * 12} {'-' * 10}")

        for cond_name in CONDITION_ORDER:
            if cond_name not in conditions:
                continue
            rows = conditions[cond_name]
            mean, std = summarise_condition(rows, metric_key)
            lines.append(f"  {cond_name:<20} {mean:>10.2f} {f'+- {std:.2f}':>12} {len(rows):>10}")

    if scipy_stats is not None and "bandit_adaptive" in conditions:
        lines.append(f"\n{'=' * 80}")
        lines.append("  Paired T-Tests: bandit_adaptive vs. baselines")
        lines.append("=" * 80)

        bandit_rows = conditions["bandit_adaptive"]
        for baseline in ["baseline_cfs", "static_naive", "heuristic_only"]:
            if baseline not in conditions:
                continue
            lines.append(f"\n  -- bandit_adaptive vs {baseline} --")
            lines.append(f"  {'Metric':<30} {'t-stat':>10} {'p-value':>10} {'Significant':>12}")
            lines.append(f"  {'-' * 30} {'-' * 10} {'-' * 10} {'-' * 12}")

            for metric_key, metric_label in metrics:
                t_stat, p_val = paired_ttest(conditions[baseline], bandit_rows, metric_key)
                if t_stat is not None and p_val is not None:
                    sig = "Yes (p<0.05)" if p_val < 0.05 else "No"
                    lines.append(f"  {metric_label:<30} {t_stat:>10.3f} {p_val:>10.4f} {sig:>12}")
                else:
                    lines.append(f"  {metric_label:<30} {'N/A':>10} {'N/A':>10} {'N/A':>12}")

    improvements = compute_relative_improvements(conditions)
    if improvements:
        lines.append(f"\n{'=' * 80}")
        lines.append("  Relative Improvement (bandit_adaptive vs baselines)")
        lines.append("=" * 80)
        for base, pct in improvements.items():
            if pct is not None:
                lines.append(f"  vs {base:<20}: {pct:>+.1f}% involuntary ctx switches")
            else:
                lines.append(f"  vs {base:<20}: N/A (baseline is 0)")

    lines.append(f"\n{'=' * 80}")
    lines.append("  Analysis complete.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_markdown_table(
    conditions: dict[str, list[dict[str, Any]]],
    include_ttest: bool = True,
) -> str:
    """Format comparative evaluation metrics into a publication-ready Markdown table."""
    lines: list[str] = [
        "| Condition | Mean CPU Load | Mean Involuntary Context Switches | Jain's Fairness | Heavy Task Completion Time |",
        "|---|---|---|---|---|",
    ]

    for cond in CONDITION_ORDER:
        if cond not in conditions:
            continue
        rows = conditions[cond]
        cpu_m, cpu_s = summarise_condition(rows, "mean_cpu_pct")
        invol_m, invol_s = summarise_condition(rows, "mean_invol_ctx_switches")
        jain_m, jain_s = summarise_condition(rows, "jain_fairness_index")
        time_m, time_s = summarise_condition(rows, "heavy_task_completion_time")

        lines.append(
            f"| `{cond}` | {cpu_m:.1f}% (+-{cpu_s:.1f}) | {invol_m:.1f} (+-{invol_s:.1f}) | {jain_m:.2f} (+-{jain_s:.2f}) | {time_m:.1f}s (+-{time_s:.1f}) |"
        )

    if include_ttest and scipy_stats is not None and "bandit_adaptive" in conditions:
        lines.append("\n### Paired T-Tests (vs `bandit_adaptive`)\n")
        bandit_rows = conditions["bandit_adaptive"]
        for base in ["baseline_cfs", "static_naive", "heuristic_only"]:
            if base in conditions and len(conditions[base]) == len(bandit_rows):
                _, p_time = paired_ttest(
                    conditions[base], bandit_rows, "heavy_task_completion_time"
                )
                _, p_invol = paired_ttest(conditions[base], bandit_rows, "mean_invol_ctx_switches")
                p_t_str = f"{p_time:.4f}" if p_time is not None else "N/A"
                p_i_str = f"{p_invol:.4f}" if p_invol is not None else "N/A"
                lines.append(
                    f"- **{base}**: Completion Time p={p_t_str}, Involuntary Switches p={p_i_str}"
                )

    return "\n".join(lines)


def format_json_summary(
    conditions: dict[str, list[dict[str, Any]]],
) -> str:
    """Format aggregated metrics as a JSON string."""
    summary: dict[str, Any] = {}
    for cond in CONDITION_ORDER:
        if cond not in conditions:
            continue
        rows = conditions[cond]
        cpu_m, cpu_s = summarise_condition(rows, "mean_cpu_pct")
        invol_m, invol_s = summarise_condition(rows, "mean_invol_ctx_switches")
        jain_m, jain_s = summarise_condition(rows, "jain_fairness_index")
        time_m, time_s = summarise_condition(rows, "heavy_task_completion_time")

        summary[cond] = {
            "mean_cpu_pct": round(cpu_m, 2),
            "std_cpu_pct": round(cpu_s, 2),
            "mean_invol_ctx_switches": round(invol_m, 2),
            "std_invol_ctx_switches": round(invol_s, 2),
            "jain_fairness_index": round(jain_m, 4),
            "std_jain_fairness_index": round(jain_s, 4),
            "heavy_task_completion_time_s": round(time_m, 2),
            "std_heavy_task_completion_time_s": round(time_s, 2),
            "n_trials": len(rows),
        }
    return json.dumps(summary, indent=2)


def parse_log_text(log_text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse legacy or evaluation stdout logs into condition records."""
    data: dict[str, list[dict[str, Any]]] = {}
    current_cond: str | None = None

    for line in log_text.splitlines():
        if "CONDITION:" in line:
            current_cond = line.split("CONDITION:")[-1].strip()
            if current_cond not in data:
                data[current_cond] = []
        elif "Mean CPU:" in line and current_cond:
            pattern = (
                r"Mean CPU:\s*([0-9.]+)%\s*\|\s*"
                r"Mean Invol Ctx:\s*([0-9.]+)\s*\|\s*"
                r"Jain:\s*([0-9.]+)\s*\|\s*"
                r"Heavy Comp Time:\s*([0-9.]+)s"
            )
            m = re.search(pattern, line)
            if m:
                data[current_cond].append(
                    {
                        "condition": current_cond,
                        "mean_cpu_pct": float(m.group(1)),
                        "mean_invol_ctx_switches": float(m.group(2)),
                        "jain_fairness_index": float(m.group(3)),
                        "heavy_task_completion_time": float(m.group(4)),
                    }
                )
    return data


def main() -> None:
    """CLI entry point for aidax-analysis."""
    parser = argparse.ArgumentParser(
        description="AI-DAX Lite: Results Summary & Statistical Analysis"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="results/results.csv",
        help="Input path to results.csv (default: results/results.csv)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output report format (default: text)",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=None,
        help="Only analyze the last N trials (default: all)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional file path to write output",
    )
    args = parser.parse_args()

    # Fallback to results.csv in current dir if default not found
    input_path = args.input
    if not os.path.exists(input_path) and os.path.exists("results.csv"):
        input_path = "results.csv"

    try:
        conditions = load_results(input_path, tail_n=args.tail)
    except FileNotFoundError:
        print(f"ERROR: {input_path} not found. Run evaluate first.", file=sys.stderr)
        sys.exit(1)

    if args.format == "markdown":
        output_str = format_markdown_table(conditions)
    elif args.format == "json":
        output_str = format_json_summary(conditions)
    else:
        output_str = format_text_report(conditions)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Analysis written to {args.output}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
