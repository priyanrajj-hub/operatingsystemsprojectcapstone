from __future__ import annotations

import os

import psutil

from aidax.workload import (
    heavy_worker_finite,
    light_worker_finite,
    spawn_workload,
    terminate_workers,
)


def test_heavy_worker_finite() -> None:
    # Prime numbers up to 30: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29 (count = 10)
    prime_count = heavy_worker_finite(30)
    assert prime_count == 10


def test_light_worker_finite() -> None:
    # Run 2 quick cycles to verify file creation, read, write, and removal
    light_worker_finite(n_cycles=2)


def test_spawn_and_terminate_workers_reaped() -> None:
    test_pid_file = "test_pids.txt"
    spawned = spawn_workload(n_heavy=1, m_light=1, finite=False, pid_file=test_pid_file)
    assert len(spawned) == 2
    pids = [p.pid for p, _ in spawned if p.pid is not None]
    assert len(pids) == 2

    for pid in pids:
        assert psutil.pid_exists(pid)

    terminate_workers([p for p, _ in spawned], pid_file=test_pid_file)

    for pid in pids:
        if psutil.pid_exists(pid):
            p = psutil.Process(pid)
            assert not p.is_running() or p.status() == psutil.STATUS_ZOMBIE

    assert not os.path.exists(test_pid_file)
