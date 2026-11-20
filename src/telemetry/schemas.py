"""
Canonical Pydantic v2 schemas for telemetry data, decisions, and WebSocket packets.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProcessMetricSnapshot(BaseModel):
    """Snapshot of resource metrics for an individual managed process."""

    model_config = ConfigDict(frozen=True)

    pid: int
    name: str = ""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    num_threads: int = 1
    core_affinity: list[int] = Field(default_factory=list)
    core_type: str = "UNKNOWN"
    workload_type: str = "UNKNOWN"


class SchedulingDecisionPacket(BaseModel):
    """Packet emitted when a scheduling decision is executed."""

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(default_factory=time.time)
    pid: int
    process_name: str = ""
    workload_type: str = "UNKNOWN"
    core_allocated: int
    core_type: str  # "PERFORMANCE" or "EFFICIENCY"
    action_chosen: int  # 0: E-core, 1: P-core
    confidence_score: float = 0.0
    reward: float | None = None
    exploration_bonus: float = 0.0
    execution_time_ms: float = 0.0


class SystemHealthSnapshot(BaseModel):
    """System-level hardware and telemetry snapshot."""

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(default_factory=time.time)
    total_cpu_percent: float
    memory_percent: float
    per_cpu_percent: list[float] = Field(default_factory=list)
    p_core_utilization: float = 0.0
    e_core_utilization: float = 0.0
    jain_fairness_index: float = 1.0
    estimated_power_watts: float = 0.0
    active_processes_count: int = 0


class LiveWebSocketMessage(BaseModel):
    """Structured message frame broadcast over live WebSocket streaming channels."""

    model_config = ConfigDict(frozen=True)

    message_type: Literal[
        "TELEMETRY", "DECISION", "HEARTBEAT", "SECURITY_ALERT", "EXPERIMENT_STATUS"
    ]
    timestamp: float = Field(default_factory=time.time)
    data: dict[str, Any] = Field(default_factory=dict)
