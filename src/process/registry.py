"""
Secure in-memory process registry tracking managed workload metadata and ownership.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

import psutil

from core.exceptions import ProcessAuthorizationError
from process.lifecycle import ProcessState

logger = logging.getLogger("aidax.process.registry")


@dataclass
class ManagedProcess:
    """Metadata representing an application-owned scheduled workload."""

    pid: int
    workload_type: str  # 'Heavy' or 'Light'
    experiment_id: str
    create_time: float
    state: ProcessState = ProcessState.REGISTERED
    original_affinity: list[int] = field(default_factory=list)
    current_affinity: list[int] = field(default_factory=list)
    registered_at: float = field(default_factory=time.time)


class ProcessRegistry:
    """Thread-safe registry of managed workloads."""

    def __init__(self, pid_file: str = "pids.txt") -> None:
        self.pid_file = pid_file
        self._processes: dict[int, ManagedProcess] = {}

    def register(
        self,
        pid: int,
        workload_type: str,
        experiment_id: str = "default",
        original_affinity: list[int] | None = None,
    ) -> ManagedProcess:
        """Register a freshly created process and capture its original affinity."""
        try:
            p = psutil.Process(pid)
            start_time = p.create_time()
            if original_affinity is None:
                try:
                    original_affinity = p.cpu_affinity()
                except Exception:
                    original_affinity = list(range(os.cpu_count() or 4))
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            raise ProcessAuthorizationError(f"Cannot inspect process {pid}: {e}") from e

        record = ManagedProcess(
            pid=pid,
            workload_type=workload_type,
            experiment_id=experiment_id,
            create_time=start_time,
            state=ProcessState.REGISTERED,
            original_affinity=original_affinity or [],
            current_affinity=original_affinity or [],
        )
        self._processes[pid] = record
        self._sync_to_file()
        logger.info("Registered PID %d (%s) for experiment %s", pid, workload_type, experiment_id)
        return record

    def unregister(self, pid: int) -> ManagedProcess | None:
        """Remove a process from registry upon completion or termination."""
        proc = self._processes.pop(pid, None)
        self._sync_to_file()
        return proc

    def get_valid_active_processes(self) -> list[ManagedProcess]:
        """
        Return active managed processes, verifying PID validity against OS create_time.
        Removes any zombie or recycled PIDs automatically.
        """
        valid: list[ManagedProcess] = []
        to_remove: list[int] = []

        for pid, record in list(self._processes.items()):
            try:
                p = psutil.Process(pid)
                if abs(p.create_time() - record.create_time) > 0.1:
                    logger.warning("PID %d has been recycled by OS! Evicting.", pid)
                    to_remove.append(pid)
                    continue

                if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                    record.state = ProcessState.COMPLETED
                    continue

                record.state = ProcessState.RUNNING
                valid.append(record)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                to_remove.append(pid)

        for pid in to_remove:
            self._processes.pop(pid, None)

        if to_remove:
            self._sync_to_file()

        return valid

    def get_by_pid(self, pid: int) -> ManagedProcess | None:
        """Fetch managed process record."""
        return self._processes.get(pid)

    def _sync_to_file(self) -> None:
        """Sync active processes to PID file for backward compatibility."""
        try:
            with open(self.pid_file, "w", encoding="utf-8") as f:
                for proc in self._processes.values():
                    f.write(
                        json.dumps({
                            "pid": proc.pid,
                            "type": proc.workload_type,
                            "start_time": proc.create_time,
                            "experiment_id": proc.experiment_id,
                        })
                        + "\n"
                    )
        except Exception as e:
            logger.debug("Could not sync PID file: %s", e)

    def clear(self) -> None:
        """Clear all registered processes."""
        self._processes.clear()
        if os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
            except OSError:
                pass
