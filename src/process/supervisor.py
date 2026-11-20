"""
Process supervisor managing workload lifecycle, execution, and safe cleanup.
"""

from __future__ import annotations

import logging
import multiprocessing
from collections.abc import Callable
from typing import Any

from core.exceptions import ProcessControlError
from process.affinity import AffinityController
from process.registry import ManagedProcess, ProcessRegistry

logger = logging.getLogger("aidax.process.supervisor")


class ProcessSupervisor:
    """Supervises managed processes, scheduling decisions, and affinity lifecycle."""

    def __init__(self, pid_file: str = "pids.txt") -> None:
        self.registry = ProcessRegistry(pid_file=pid_file)
        self.affinity_controller = AffinityController()
        self._spawned_procs: list[multiprocessing.Process] = []

    def spawn_managed_worker(
        self,
        target_func: Callable[..., Any],
        args: tuple[Any, ...],
        workload_type: str,
        experiment_id: str = "default",
    ) -> ManagedProcess:
        """Spawn a child worker process and immediately register it under supervision."""
        proc = multiprocessing.Process(target=target_func, args=args)
        proc.start()
        if proc.pid is None:
            raise ProcessControlError("Process failed to start and has no PID")
        self._spawned_procs.append(proc)

        managed = self.registry.register(
            pid=proc.pid,
            workload_type=workload_type,
            experiment_id=experiment_id,
        )
        return managed

    def terminate_all(self, timeout: float = 3.0) -> None:
        """Gracefully restore affinities and terminate all supervised processes."""
        logger.info("Supervisor terminating all managed processes...")
        active = self.registry.get_valid_active_processes()
        self.affinity_controller.emergency_reset(active)

        for p in self._spawned_procs:
            if p.is_alive():
                p.terminate()
                p.join(timeout=timeout)

        self._spawned_procs.clear()
        self.registry.clear()
        logger.info("All supervised processes cleanly terminated.")
