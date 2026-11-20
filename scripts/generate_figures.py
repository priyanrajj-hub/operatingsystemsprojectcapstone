#!/usr/bin/env python3
"""
Publication-Quality Figure and LaTeX Macro Generator.

Reads raw/processed benchmark JSON data and generates:
  - Vector PDFs (colorblind-safe, matplotlib, publication styling)
  - results_macros.tex containing auto-generated LaTeX commands
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.generate_figures")

# Styling: IEEE-ready publication style
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "figure.autolayout": True,
        "lines.linewidth": 1.5,
    }
)


def generate_regret_figure(sim_data_file: Path, out_pdf: Path) -> None:
    """Generate Cumulative Regret comparison curve."""
    if not sim_data_file.exists():
        logger.warning("File %s does not exist; skipping regret figure.", sim_data_file)
        return

    with open(sim_data_file, encoding="utf-8") as f:
        data = json.load(f)

    fig, ax = plt.subplots(figsize=(3.4, 2.4))

    steps_linucb = range(len(data["linucb"]["mean_regret_curve"]))
    mean_linucb = np.array(data["linucb"]["mean_regret_curve"])
    std_linucb = np.array(data["linucb"]["std_regret_curve"])

    ax.plot(steps_linucb, mean_linucb, label="LinUCB (Ours)", color="#1f77b4")
    ax.fill_between(
        steps_linucb,
        np.maximum(0, mean_linucb - std_linucb),
        mean_linucb + std_linucb,
        alpha=0.2,
        color="#1f77b4",
    )

    if "thompson_sampling" in data:
        steps_ts = range(len(data["thompson_sampling"]["mean_regret_curve"]))
        mean_ts = np.array(data["thompson_sampling"]["mean_regret_curve"])
        std_ts = np.array(data["thompson_sampling"]["std_regret_curve"])
        ax.plot(steps_ts, mean_ts, label="LinTS Baseline", color="#ff7f0e", linestyle="--")
        ax.fill_between(
            steps_ts, np.maximum(0, mean_ts - std_ts), mean_ts + std_ts, alpha=0.15, color="#ff7f0e"
        )

    ax.set_xlabel("Decision Epoch $t$")
    ax.set_ylabel("Cumulative Regret $\\mathcal{R}(t)$")
    ax.set_title("Regret vs Known Linear Ground Truth")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", frameon=True)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, format="pdf", dpi=300)
    plt.close(fig)
    logger.info("Saved %s", out_pdf)


def generate_overhead_figure(bench_file: Path, out_pdf: Path) -> None:
    """Generate Decision Latency vs Process Scale figure."""
    if not bench_file.exists():
        return

    with open(bench_file, encoding="utf-8") as f:
        data = json.load(f)

    n_vals = [data[k]["n_processes"] for k in data]
    means = [data[k]["mean_decision_latency_us"] for k in data]
    p95s = [data[k]["p95_decision_latency_us"] for k in data]

    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    ax.plot(n_vals, means, marker="o", label="Mean Latency ($\\mu$s)", color="#2ca02c")
    ax.plot(
        n_vals, p95s, marker="s", linestyle="--", label="P95 Latency ($\\mu$s)", color="#d62728"
    )

    ax.set_xlabel("Managed Processes ($N$)")
    ax.set_ylabel("Decision Latency ($\\mu$s)")
    ax.set_title("User-Space Scheduler Overhead")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="center right", frameon=True)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, format="pdf", dpi=300)
    plt.close(fig)
    logger.info("Saved %s", out_pdf)


def generate_adversarial_figure(adv_file: Path, out_pdf: Path) -> None:
    """Generate Adversarial Impact & Recovery bar chart."""
    if not adv_file.exists():
        return

    with open(adv_file, encoding="utf-8") as f:
        data = json.load(f)

    labels = ["Clean Baseline", "Under Attack\n(No Defense)", "Under Attack\n(Mitigated)"]
    ratios = [
        data["clean_baseline"]["optimal_p_core_allocation_ratio"] * 100.0,
        data["attacked_without_defense"]["optimal_p_core_allocation_ratio"] * 100.0,
        data["attacked_with_defense"]["optimal_p_core_allocation_ratio"] * 100.0,
    ]
    colors = ["#1f77b4", "#d62728", "#2ca02c"]

    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    bars = ax.bar(labels, ratios, color=colors, width=0.55, edgecolor="black", linewidth=0.5)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(
            f"{h:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.5,
        )

    ax.set_ylabel("Optimal Allocation Ratio (%)")
    ax.set_ylim(0, 115)
    ax.set_title("Adversarial Robustness & Defense")
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, format="pdf", dpi=300)
    plt.close(fig)
    logger.info("Saved %s", out_pdf)


def generate_latex_macros(processed_dir: Path, out_macro_file: Path) -> None:
    """Generate results_macros.tex ensuring zero numbers are hand-copied."""
    macros: list[str] = ["% Auto-generated LaTeX macros from empirical experimental data"]

    # 1. Simulator data
    sim_file = processed_dir / "sim_regret.json"
    if sim_file.exists():
        with open(sim_file, encoding="utf-8") as f:
            sim = json.load(f)
        macros.append(
            f"\\newcommand{{\\LinUCBFinalRegret}}{{{sim['linucb']['final_cumulative_regret']:.1f}}}"
        )
        if "thompson_sampling" in sim:
            macros.append(
                f"\\newcommand{{\\TSFinalRegret}}{{{sim['thompson_sampling']['final_cumulative_regret']:.1f}}}"
            )

    # 2. Overhead benchmark
    overhead_file = processed_dir / "overhead_bench.json"
    if overhead_file.exists():
        with open(overhead_file, encoding="utf-8") as f:
            ovh = json.load(f)
        mean_16 = ovh.get("N_16", {}).get("mean_decision_latency_us", 0.0)
        p95_16 = ovh.get("N_16", {}).get("p95_decision_latency_us", 0.0)
        rss_16 = ovh.get("N_16", {}).get("rss_memory_mb", 0.0)
        macros.append(f"\\newcommand{{\\MeanLatencyUsSixteen}}{{{mean_16:.1f}}}")
        macros.append(f"\\newcommand{{\\PninetyfiveLatencyUsSixteen}}{{{p95_16:.1f}}}")
        macros.append(f"\\newcommand{{\\RssDeltaMbSixteen}}{{{rss_16:.1f}}}")

    # 3. Adversarial benchmark
    adv_file = processed_dir / "adversarial_results.json"
    if adv_file.exists():
        with open(adv_file, encoding="utf-8") as f:
            adv = json.load(f)
        recovery = adv.get("attacked_with_defense", {}).get("recovery_pct", 100.0)
        macros.append(f"\\newcommand{{\\AdversarialRecoveryPct}}{{{recovery:.1f}}}")

    out_macro_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_macro_file, "w", encoding="utf-8") as f:
        f.write("\n".join(macros) + "\n")
    logger.info("Saved %s (%d macros generated)", out_macro_file, len(macros) - 1)


def main() -> None:
    data_dir = Path("data/processed")
    paper_dir = Path("paper")
    generate_regret_figure(data_dir / "sim_regret.json", paper_dir / "figures" / "fig_regret.pdf")
    generate_overhead_figure(
        data_dir / "overhead_bench.json", paper_dir / "figures" / "fig_overhead.pdf"
    )
    generate_adversarial_figure(
        data_dir / "adversarial_results.json", paper_dir / "figures" / "fig_adversarial.pdf"
    )
    generate_latex_macros(data_dir, paper_dir / "results_macros.tex")


if __name__ == "__main__":
    main()
