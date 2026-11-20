#!/usr/bin/env python3
"""
Scheduler Overhead and Scalability Benchmark.

Measures decision latency (microseconds), resident memory (MB),
and throughput overhead as managed process count scales from N=2 to N=32.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from scheduler.linucb import StableLinUCBBandit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.bench_overhead")


def benchmark_decision_latency(
    n_processes_list: list[int] | None = None, n_iterations: int = 1000
) -> dict[str, Any]:
    """Measure LinUCB action selection and update latency under scale."""
    if n_processes_list is None:
        n_processes_list = [2, 4, 8, 16, 32]
    bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0, num_arms=3, seed=42)
    rng = np.random.default_rng(1234)
    results: dict[str, Any] = {}

    proc = psutil.Process()
    base_rss_mb = proc.memory_info().rss / (1024.0 * 1024.0)

    for n_pids in n_processes_list:
        contexts = rng.random((n_pids, 4))
        rewards = rng.uniform(-1.0, 1.0, size=n_pids)

        # Benchmark decision selection latency
        latencies_us: list[float] = []
        for _ in range(n_iterations):
            for i in range(n_pids):
                t0 = time.perf_counter_ns()
                action, _ = bandit.select_action(contexts[i])
                t1 = time.perf_counter_ns()
                latencies_us.append((t1 - t0) / 1000.0)

                # Periodic update
                bandit.update(action, contexts[i], float(rewards[i]))

        current_rss_mb = proc.memory_info().rss / (1024.0 * 1024.0)
        mean_lat = float(np.mean(latencies_us))
        p95_lat = float(np.percentile(latencies_us, 95))
        p99_lat = float(np.percentile(latencies_us, 99))

        results[f"N_{n_pids}"] = {
            "n_processes": n_pids,
            "mean_decision_latency_us": round(mean_lat, 2),
            "p95_decision_latency_us": round(p95_lat, 2),
            "p99_decision_latency_us": round(p99_lat, 2),
            "rss_memory_mb": round(current_rss_mb - base_rss_mb, 2),
            "total_decisions_benchmarked": len(latencies_us),
        }
        logger.info(
            "Scale N=%d: Mean Latency=%.2f us, P95=%.2f us, Memory Delta=%.2f MB",
            n_pids,
            mean_lat,
            p95_lat,
            current_rss_mb - base_rss_mb,
        )

    return results


def main() -> None:
    res = benchmark_decision_latency()
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "overhead_bench.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    logger.info("Overhead benchmark saved to %s", out_file)


if __name__ == "__main__":
    main()
