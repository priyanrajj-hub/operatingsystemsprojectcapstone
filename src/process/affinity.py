"""
CPU core affinity controller with cross-platform safety and emergency recovery.
"""

from __future__ import annotations

import logging
import os
import sys

import psutil

from process.registry import ManagedProcess

logger = logging.getLogger("aidax.process.affinity")


def set_process_affinity(pid: int, cpus: list[int]) -> bool:
    """
    Safely set affinity for a PID with platform guards.
    Returns False gracefully on macOS or systems where cpu_affinity is unsupported.
    """
    try:
        p = psutil.Process(pid)
        if not hasattr(p, "cpu_affinity"):
            logger.info("cpu_affinity not supported on platform %s; skipping.", sys.platform)
            return False
        p.cpu_affinity(cpus)
        return True
    except Exception as e:
        logger.debug("Failed setting affinity for PID %d: %s", pid, e)
        return False


class AffinityController:
    """Manages CPU core binding for authorized workload processes."""

    def __init__(self, total_cores: int | None = None) -> None:
        self.total_cores = total_cores or os.cpu_count() or 4
        self.all_cores = list(range(self.total_cores))

    def set_affinity(self, managed_proc: ManagedProcess, target_cores: list[int]) -> bool:
        """Apply target core affinity to an authorized managed process."""
        if not target_cores:
            return False

        try:
            p = psutil.Process(managed_proc.pid)
            # Revalidate identity immediately before modification
            if abs(p.create_time() - managed_proc.create_time) > 0.1:
                logger.error(
                    "PID %d revalidated create_time mismatch! Refusing affinity change.",
                    managed_proc.pid,
                )
                return False

            if hasattr(p, "cpu_affinity"):
                p.cpu_affinity(target_cores)
                managed_proc.current_affinity = list(target_cores)
                return True
            else:
                logger.debug("cpu_affinity not supported on this platform (e.g. macOS).")
                return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError) as e:
            logger.debug("Failed setting affinity on PID %d: %s", managed_proc.pid, e)
            return False

    def restore_affinity(self, managed_proc: ManagedProcess) -> bool:
        """Restore process to its original captured CPU affinity."""
        target = (
            managed_proc.original_affinity if managed_proc.original_affinity else self.all_cores
        )
        return self.set_affinity(managed_proc, target)

    def emergency_reset(self, managed_procs: list[ManagedProcess]) -> int:
        """Release affinity constraints across all managed processes, binding to all cores."""
        count = 0
        for proc in managed_procs:
            if self.set_affinity(proc, self.all_cores):
                count += 1
        logger.info("Emergency affinity reset released %d process(es) to all cores.", count)
        return count
