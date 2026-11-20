"""
Hardware topology inspection endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from hardware.detection import detect_cpu_topology

router = APIRouter(prefix="/api/v1/hardware", tags=["Hardware"])


@router.get("/topology")
async def get_hardware_topology() -> dict[str, Any]:
    """Retrieve detected heterogeneous or simulated CPU topology."""
    topo = detect_cpu_topology()
    return {
        "total_logical_cores": topo.total_logical_cores,
        "total_physical_cores": topo.total_physical_cores,
        "is_heterogeneous": topo.is_heterogeneous,
        "detection_method": topo.detection_method,
        "confidence": topo.confidence,
        "performance_cores": topo.p_cores,
        "efficiency_cores": topo.e_cores,
    }
