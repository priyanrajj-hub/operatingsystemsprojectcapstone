"""
Process lifecycle state definitions for managed workloads.
"""

from __future__ import annotations

from enum import Enum


class ProcessState(str, Enum):
    """Lifecycle states of an AI-DAX managed workload."""

    CREATED = "CREATED"
    REGISTERED = "REGISTERED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"
