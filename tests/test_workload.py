from __future__ import annotations

from aidax.workload import heavy_worker_finite, light_worker_finite


def test_heavy_worker_finite() -> None:
    # Prime numbers up to 30: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29 (count = 10)
    prime_count = heavy_worker_finite(30)
    assert prime_count == 10


def test_light_worker_finite() -> None:
    # Run 2 quick cycles to verify file creation, read, write, and removal
    light_worker_finite(n_cycles=2)
