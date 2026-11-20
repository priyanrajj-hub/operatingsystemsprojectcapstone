"""
Benign local adversarial workload kernels for robustness and security evaluations.

Simulates adversarial process strategies:
  (a) Context-Switch Inflator: Rapid sched_yield loop to manipulate involuntary switch counters.
  (b) CPU Spoofer: High-frequency duty-cycle shaping to deceive average utilization estimators.
  (c) Feature Mimic: CPU-heavy worker masking its resource profile.
  (d) Reward Poisoner: Deliberately induced noise and latency.
"""

from __future__ import annotations

import logging
import math
import time

import numpy as np

logger = logging.getLogger("aidax.security.adversarial")


def context_switch_inflator_kernel(duration_seconds: float = 5.0) -> int:
    """Benign local process that invokes rapid voluntary context switches via sleep(0)."""
    start = time.time()
    switches = 0
    while time.time() - start < duration_seconds:
        time.sleep(0.0001)
        switches += 1
    return switches


def cpu_spoofer_kernel(
    duration_seconds: float = 5.0, duty_cycle: float = 0.5, period_ms: float = 50.0
) -> int:
    """Duty-cycle shaper alternating 100% active spin with idle sleep to spoof mean metrics."""
    start = time.time()
    cycles = 0
    period_s = period_ms / 1000.0
    active_s = period_s * duty_cycle
    sleep_s = period_s * (1.0 - duty_cycle)

    while time.time() - start < duration_seconds:
        t_end = time.time() + active_s
        x = 1.0001
        while time.time() < t_end:
            x = math.sin(x) * math.cos(x)
        if sleep_s > 0:
            time.sleep(sleep_s)
        cycles += 1
    return cycles


def feature_mimicry_kernel(duration_seconds: float = 5.0) -> int:
    """Heavy computational task disguised with bursty pauses to mimic an interactive process."""
    start = time.time()
    rng = np.random.default_rng(777)
    chunks = 0
    while time.time() - start < duration_seconds:
        a = rng.random((100, 100))
        b = rng.random((100, 100))
        _ = np.dot(a, b)
        time.sleep(0.02)
        chunks += 1
    return chunks
