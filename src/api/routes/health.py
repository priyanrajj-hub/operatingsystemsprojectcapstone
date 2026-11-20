"""
Health and readiness probe endpoints.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["Health"])
START_TIME = time.time()


@router.get("/health")
@router.get("/api/v1/health")
async def get_health() -> dict[str, Any]:
    """Liveness and readiness health probe."""
    uptime_sec = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "service": "ai-dax-lite",
        "version": "1.0.0",
        "uptime_seconds": uptime_sec,
        "timestamp": time.time(),
    }
