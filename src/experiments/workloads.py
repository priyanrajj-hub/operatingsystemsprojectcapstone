"""
Reproducible synthetic workload kernels representing heterogeneous compute patterns.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time

import numpy as np

logger = logging.getLogger("aidax.experiments.workloads")


def cpu_intensive_kernel(duration_seconds: float = 10.0, matrix_size: int = 150) -> int:
    """CPU-bound task performing continuous matrix multiplications."""
    start_time = time.time()
    iterations = 0
    rng = np.random.default_rng(42)
    a = rng.random((matrix_size, matrix_size))
    b = rng.random((matrix_size, matrix_size))

    while time.time() - start_time < duration_seconds:
        _ = np.dot(a, b)
        iterations += 1
    return iterations


def memory_intensive_kernel(duration_seconds: float = 10.0, array_mb: int = 32) -> int:
    """Memory-bound task inducing cache misses through strided random array reads."""
    start_time = time.time()
    iterations = 0
    size = (array_mb * 1024 * 1024) // 8
    rng = np.random.default_rng(123)
    data = rng.integers(0, 1000, size=size, dtype=np.int64)
    indices = rng.integers(0, size, size=min(size, 500000), dtype=np.int64)

    total = 0
    while time.time() - start_time < duration_seconds:
        chunk = data[indices[:10000]]
        total += int(np.sum(chunk))
        iterations += 1
    return iterations


def io_intensive_kernel(duration_seconds: float = 10.0, chunk_kb: int = 64) -> int:
    """I/O-bound task performing sequential file writes and flushes."""
    start_time = time.time()
    iterations = 0
    payload = b"X" * (chunk_kb * 1024)

    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_name = f.name
        try:
            while time.time() - start_time < duration_seconds:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
                f.seek(0)
                iterations += 1
        finally:
            f.close()
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    return iterations


def bursty_kernel(
    duration_seconds: float = 10.0, compute_slice_s: float = 0.2, sleep_slice_s: float = 0.3
) -> int:
    """Bursty task alternating high CPU bursts with idle sleep."""
    start_time = time.time()
    burst_count = 0
    rng = np.random.default_rng(999)

    while time.time() - start_time < duration_seconds:
        burst_end = time.time() + compute_slice_s
        while time.time() < burst_end:
            _ = np.linalg.norm(rng.random(1000))
        burst_count += 1
        time.sleep(sleep_slice_s)
    return burst_count
