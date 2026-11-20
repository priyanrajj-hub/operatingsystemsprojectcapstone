"""
AI-DAX Lite: Workload Generator
================================
Spawns a configurable mix of CPU-bound (Heavy) and I/O-bound (Light) worker
processes. Supports both infinite-loop mode (for live dashboard demos) and
finite-job mode (for reproducible evaluation benchmarks).

Finite mode: Heavy workers compute primes up to N (default 50000), then exit.
             Light workers perform N file write/read cycles (default 500).
             Completion time is measurable for the evaluation harness.
"""

import multiprocessing
import time
import os
import json
import signal
import sys
import tempfile
import argparse
import psutil

PID_FILE = 'pids.txt'


def heavy_worker_infinite():
    """Simulates CPU-bound work using an infinite prime calculation loop."""
    while True:
        primes = []
        for possiblePrime in range(2, 5000):
            is_prime = True
            for num in range(2, possiblePrime):
                if possiblePrime % num == 0:
                    is_prime = False
                    break
            if is_prime:
                primes.append(possiblePrime)


def heavy_worker_finite(n):
    """Simulates CPU-bound work: compute primes up to N, then exit."""
    primes = []
    for possiblePrime in range(2, n):
        is_prime = True
        for num in range(2, int(possiblePrime ** 0.5) + 1):
            if possiblePrime % num == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(possiblePrime)
    return len(primes)


def light_worker_infinite():
    """Simulates I/O-bound work with small file writes/reads and sleeps."""
    temp_file = tempfile.mktemp()
    try:
        while True:
            with open(temp_file, 'w') as f:
                f.write("a" * 1024 * 10)
            time.sleep(0.5)
            with open(temp_file, 'r') as f:
                f.read()
            time.sleep(0.5)
    finally:
        try:
            os.remove(temp_file)
        except OSError:
            pass


def light_worker_finite(n_cycles):
    """Simulates I/O-bound work: N file write/read cycles, then exit."""
    temp_file = tempfile.mktemp()
    try:
        for _ in range(n_cycles):
            with open(temp_file, 'w') as f:
                f.write("a" * 1024 * 10)
            time.sleep(0.1)
            with open(temp_file, 'r') as f:
                f.read()
            time.sleep(0.1)
    finally:
        try:
            os.remove(temp_file)
        except OSError:
            pass


workers = []


def cleanup(signum=None, frame=None):
    """Gracefully terminates worker processes on exit."""
    print("\n[WORKLOAD GENERATOR] Stopping workers...")
    for w in workers:
        if w.is_alive():
            w.terminate()
            w.join(timeout=5)
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
    sys.exit(0)


def spawn_workload(n_heavy=2, m_light=2, finite=False, heavy_n=4000000,
                   light_cycles=200):
    """
    Spawn worker processes and register them in pids.txt.
    Returns list of (Process, type_label) tuples.
    """
    global workers
    workers = []

    # Initialise the tracking file
    with open(PID_FILE, 'w') as f:
        pass

    print(f"[WORKLOAD GENERATOR] Spawning {n_heavy} Heavy + {m_light} Light "
          f"({'finite' if finite else 'infinite'} mode)")

    spawned = []
    for i in range(n_heavy + m_light):
        w_type = 'Heavy' if i < n_heavy else 'Light'
        if finite:
            if w_type == 'Heavy':
                target = heavy_worker_finite
                args = (heavy_n,)
            else:
                target = light_worker_finite
                args = (light_cycles,)
        else:
            target = heavy_worker_infinite if w_type == 'Heavy' else light_worker_infinite
            args = ()

        p = multiprocessing.Process(target=target, args=args)
        p.start()
        workers.append(p)
        spawned.append((p, w_type))

        # Save exact creation time for robust PID-reuse validation
        start_time = psutil.Process(p.pid).create_time()
        with open(PID_FILE, 'a') as f:
            f.write(json.dumps({
                'pid': p.pid,
                'type': w_type,
                'start_time': start_time
            }) + '\n')

    print(f"[WORKLOAD GENERATOR] Running {n_heavy} Heavy and {m_light} Light processes.")
    return spawned


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI-DAX Lite Workload Generator')
    parser.add_argument('--heavy', type=int, default=2, help='Number of heavy (CPU-bound) workers')
    parser.add_argument('--light', type=int, default=2, help='Number of light (I/O-bound) workers')
    parser.add_argument('--finite', action='store_true', help='Run finite jobs instead of infinite loops')
    parser.add_argument('--heavy-n', type=int, default=4000000, help='Prime limit for finite heavy jobs')
    parser.add_argument('--light-cycles', type=int, default=200, help='I/O cycles for finite light jobs')
    args = parser.parse_args()

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    spawn_workload(
        n_heavy=args.heavy,
        m_light=args.light,
        finite=args.finite,
        heavy_n=args.heavy_n,
        light_cycles=args.light_cycles,
    )

    try:
        while True:
            # In finite mode, exit once all workers complete
            if args.finite and all(not w.is_alive() for w in workers):
                print("[WORKLOAD GENERATOR] All finite jobs completed.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()
