from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from aidax.analysis import (
    compute_relative_improvements,
    format_json_summary,
    format_markdown_table,
    format_text_report,
    holm_bonferroni_correction,
    load_results,
    paired_ttest,
    parse_log_text,
    summarise_condition,
)


def _create_sample_csv(csv_path: Path) -> None:
    headers = [
        "condition",
        "trial",
        "duration_s",
        "n_heavy",
        "n_light",
        "mean_cpu_pct",
        "mean_invol_ctx_switches",
        "median_invol_ctx_switches",
        "p95_invol_ctx_switches",
        "jain_fairness_index",
        "mean_completion_time",
        "heavy_task_completion_time",
        "n_processes_measured",
    ]
    rows = [
        ["baseline_cfs", 1, 10, 2, 2, 50.0, 100.0, 90.0, 110.0, 0.50, 10.0, 10.0, 4],
        ["baseline_cfs", 2, 10, 2, 2, 52.0, 110.0, 95.0, 120.0, 0.51, 10.0, 10.0, 4],
        ["bandit_adaptive", 1, 10, 2, 2, 45.0, 20.0, 18.0, 25.0, 0.75, 8.0, 8.0, 4],
        ["bandit_adaptive", 2, 10, 2, 2, 47.0, 25.0, 20.0, 28.0, 0.77, 7.5, 7.5, 4],
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def test_load_and_summarise(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    _create_sample_csv(csv_path)

    conditions = load_results(str(csv_path))
    assert "baseline_cfs" in conditions
    assert "bandit_adaptive" in conditions
    assert len(conditions["baseline_cfs"]) == 2

    mean_cpu, std_cpu = summarise_condition(conditions["baseline_cfs"], "mean_cpu_pct")
    assert np.isclose(mean_cpu, 51.0)
    assert std_cpu > 0.0


def test_paired_ttest_and_improvements(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    _create_sample_csv(csv_path)
    conditions = load_results(str(csv_path))

    t_stat, p_val = paired_ttest(
        conditions["baseline_cfs"],
        conditions["bandit_adaptive"],
        "mean_invol_ctx_switches",
    )
    assert t_stat is not None
    assert p_val is not None
    assert p_val <= 1.0

    improvements = compute_relative_improvements(conditions, "mean_invol_ctx_switches")
    assert "baseline_cfs" in improvements
    assert improvements["baseline_cfs"] is not None
    assert improvements["baseline_cfs"] > 50.0  # From ~105 to ~22.5 is ~78% improvement


def test_formatters(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    _create_sample_csv(csv_path)
    conditions = load_results(str(csv_path))

    text_rep = format_text_report(conditions)
    assert "Comparative Evaluation Results" in text_rep
    assert "bandit_adaptive" in text_rep

    md_table = format_markdown_table(conditions)
    assert "| Condition |" in md_table
    assert "| `bandit_adaptive` |" in md_table

    json_str = format_json_summary(conditions)
    assert '"bandit_adaptive"' in json_str


def test_parse_log_text() -> None:
    raw_log = (
        "============================================================\n"
        "  CONDITION: baseline_cfs\n"
        "============================================================\n"
        "  Trial 1/2\n"
        "    Mean CPU: 47.1% | Mean Invol Ctx: 10.5 | Jain: 0.5123 | Heavy Comp Time: 26.47s\n"
    )
    parsed = parse_log_text(raw_log)
    assert "baseline_cfs" in parsed
    assert len(parsed["baseline_cfs"]) == 1
    assert np.isclose(parsed["baseline_cfs"][0]["mean_cpu_pct"], 47.1)
    assert np.isclose(parsed["baseline_cfs"][0]["jain_fairness_index"], 0.5123)


def test_paired_ttest_zero_variance_identical() -> None:
    identical_a = [{"metric": 10.0}, {"metric": 10.0}, {"metric": 10.0}]
    identical_b = [{"metric": 10.0}, {"metric": 10.0}, {"metric": 10.0}]
    t_stat, p_val = paired_ttest(identical_a, identical_b, "metric")
    assert t_stat == 0.0
    assert p_val == 1.0


def test_analysis_holm_bonferroni() -> None:
    p_vals = [0.01, 0.04, 0.03]
    results = holm_bonferroni_correction(p_vals, family_alpha=0.05)
    assert len(results) == 3
    # Smallest p (0.01) tested against 0.05/3 = 0.0167 -> Significant
    assert results[0][1] is True
