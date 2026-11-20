"""
Telemetry and resource utilization query endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from hardware.detection import detect_cpu_topology
from process.registry import ProcessRegistry
from telemetry.collector import TelemetryCollector

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])
_topology = detect_cpu_topology()
_collector = TelemetryCollector(topology=_topology)
_registry = ProcessRegistry()


@router.get("/live")
async def get_live_telemetry() -> dict[str, Any]:
    """Sample real-time hardware health and core distributions."""
    active_procs = _registry.get_valid_active_processes()
    health = _collector.sample_system_health(active_managed_count=len(active_procs))
    return health.model_dump()


@router.get("/processes")
async def get_managed_processes() -> dict[str, Any]:
    """Retrieve resource telemetry for active managed processes."""
    active_procs = _registry.get_valid_active_processes()
    snapshots = []
    for proc in active_procs:
        snap = _collector.sample_managed_process(proc)
        if snap:
            snapshots.append(snap.model_dump())
    return {
        "count": len(snapshots),
        "processes": snapshots,
    }
