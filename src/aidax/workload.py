"""
AI-DAX Lite: Workload Generator
================================
Spawns a configurable mix of CPU-bound (Heavy) and I/O-bound (Light) worker
processes for live dashboard demonstrations and reproducible benchmarks.

Finite mode:
- Heavy workers compute primes up to N (default 4,000,000) and exit.
- Light workers execute N file read/write cycles (default 200) and exit.
- Process completion time is recorded by the evaluation harness.
"""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import os
import signal
import sys
import tempfile
import time
from collections.abc import Callable
from typing import Any

import psutil

logger = logging.getLogger("aidax.workload")
PID_FILE = "pids.txt"

_ACTIVE_WORKERS: list[multiprocessing.Process] = []


def heavy_worker_infinite() -> None:
    """CPU-bound task running an infinite prime calculation loop."""
    while True:
        primes: list[int] = []
        for possible_prime in range(2, 5000):
            is_prime = True
            for num in range(2, possible_prime):
                if possible_prime % num == 0:
                    is_prime = False
                    break
            if is_prime:
                primes.append(possible_prime)


def heavy_worker_finite(n: int) -> int:
    """CPU-bound task computing primes up to n, then terminating."""
    primes: list[int] = []
    for possible_prime in range(2, n):
        is_prime = True
        limit = int(possible_prime**0.5) + 1
        for num in range(2, limit):
            if possible_prime % num == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(possible_prime)
    return len(primes)


def light_worker_infinite() -> None:
    """I/O-bound task performing continuous write/read cycles."""
    tmp_fd, temp_file = tempfile.mkstemp(prefix=".workload_light_", suffix=".tmp")
    os.close(tmp_fd)
    payload = "a" * (1024 * 10)
    try:
        while True:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(payload)
            time.sleep(0.5)
            with open(temp_file, encoding="utf-8") as f:
                _ = f.read()
            time.sleep(0.5)
    finally:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass


def light_worker_finite(n_cycles: int) -> None:
    """I/O-bound task performing n write/read cycles, then terminating."""
    tmp_fd, temp_file = tempfile.mkstemp(prefix=".workload_light_", suffix=".tmp")
    os.close(tmp_fd)
    payload = "a" * (1024 * 10)
    try:
        for _ in range(n_cycles):
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(payload)
            time.sleep(0.1)
            with open(temp_file, encoding="utf-8") as f:
                _ = f.read()
            time.sleep(0.1)
    finally:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass


def terminate_workers(
    workers: list[multiprocessing.Process] | None = None,
    pid_file: str = PID_FILE,
) -> None:
    """Gracefully terminate worker processes and clean up tracking file."""
    target_workers = workers if workers is not None else _ACTIVE_WORKERS
    logger.info("Stopping %d workers...", len(target_workers))
    for w in target_workers:
        if w.is_alive():
            w.terminate()
            w.join(timeout=5)
    target_workers.clear()

    if os.path.exists(pid_file):
        try:
            os.remove(pid_file)
        except OSError:
            pass


def cleanup(signum: int | None = None, frame: Any | None = None) -> None:
    """Signal handler wrapper for graceful shutdown."""
    terminate_workers()
    sys.exit(0)


def spawn_workload(
    n_heavy: int = 2,
    m_light: int = 2,
    finite: bool = False,
    heavy_n: int = 4000000,
    light_cycles: int = 200,
    pid_file: str = PID_FILE,
) -> list[tuple[multiprocessing.Process, str]]:
    """
    Spawn worker processes and register their PID and creation timestamp.

    Returns:
        List of (multiprocessing.Process, type_label) tuples.
    """
    global _ACTIVE_WORKERS
    _ACTIVE_WORKERS = []

    # Reset PID tracking file
    with open(pid_file, "w", encoding="utf-8") as f:
        pass

    mode_str = "finite" if finite else "infinite"
    logger.info("Spawning %d Heavy + %d Light (%s mode)", n_heavy, m_light, mode_str)

    spawned: list[tuple[multiprocessing.Process, str]] = []
    for i in range(n_heavy + m_light):
        w_type = "Heavy" if i < n_heavy else "Light"
        target: Callable[..., Any]
        if finite:
            if w_type == "Heavy":
                target = heavy_worker_finite
                args: tuple[Any, ...] = (heavy_n,)
            else:
                target = light_worker_finite
                args = (light_cycles,)
        else:
            target = heavy_worker_infinite if w_type == "Heavy" else light_worker_infinite
            args = ()

        p = multiprocessing.Process(target=target, args=args)
        p.start()
        _ACTIVE_WORKERS.append(p)
        spawned.append((p, w_type))

        try:
            start_time = psutil.Process(p.pid).create_time()
        except Exception:
            start_time = time.time()

        with open(pid_file, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "pid": p.pid,
                        "type": w_type,
                        "start_time": start_time,
                    }
                )
                + "\n"
            )

    logger.info("Running %d Heavy and %d Light processes.", n_heavy, m_light)
    return spawned


def main() -> None:
    """CLI entry point for aidax-workload."""
    parser = argparse.ArgumentParser(description="AI-DAX Lite Workload Generator")
    parser.add_argument(
        "--heavy",
        type=int,
        default=2,
        help="Number of heavy (CPU-bound) workers (default: 2)",
    )
    parser.add_argument(
        "--light",
        type=int,
        default=2,
        help="Number of light (I/O-bound) workers (default: 2)",
    )
    parser.add_argument(
        "--finite",
        action="store_true",
        help="Run finite jobs instead of infinite loops",
    )
    parser.add_argument(
        "--heavy-n",
        type=int,
        default=4000000,
        help="Prime search limit for finite heavy jobs",
    )
    parser.add_argument(
        "--light-cycles",
        type=int,
        default=200,
        help="I/O cycles for finite light jobs",
    )
    parser.add_argument(
        "--pid-file",
        type=str,
        default=PID_FILE,
        help="Path to PID tracking file (default: pids.txt)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    )

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    spawn_workload(
        n_heavy=args.heavy,
        m_light=args.light,
        finite=args.finite,
        heavy_n=args.heavy_n,
        light_cycles=args.light_cycles,
        pid_file=args.pid_file,
    )

    try:
        while True:
            if args.finite and all(not w.is_alive() for w in _ACTIVE_WORKERS):
                logger.info("All finite jobs completed.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
