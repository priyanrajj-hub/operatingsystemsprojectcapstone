"""
Scheduler control, bandit telemetry, and AI routing endpoints.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from process.affinity import AffinityController
from process.registry import ProcessRegistry
from scheduler.linucb import StableLinUCBBandit
from security.validation import verify_api_token

router = APIRouter(prefix="/api/v1/scheduler", tags=["Scheduler"])
_registry = ProcessRegistry()
_affinity = AffinityController()
_bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0)


class RoutingRequest(BaseModel):
    """Context input payload requesting routing recommendation."""

    cpu_percent: float = Field(ge=0.0, le=100.0, default=50.0)
    memory_mb: float = Field(ge=0.0, default=128.0)
    num_threads: int = Field(ge=1, default=1)
    is_bursty: bool = False


@router.get("/stats")
async def get_scheduler_stats() -> dict[str, Any]:
    """Retrieve current contextual bandit snapshot."""
    return _bandit.get_params_snapshot()


@router.post("/reset")
async def reset_affinities(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    """
    Emergency reset: restores all managed processes to unconstrained CPU affinities.
    Requires administrative token authentication when configured.
    """
    expected_token = os.getenv("AIDAX_API_TOKEN", "")
    if expected_token:
        if not verify_api_token(x_api_token, expected_token):
            raise HTTPException(
                status_code=401, detail="Unauthorized: invalid or missing API token"
            )

    active_procs = _registry.get_valid_active_processes()
    reverted_count = _affinity.emergency_reset(active_procs)
    return {
        "status": "success",
        "message": f"Successfully restored affinity for {reverted_count} managed processes.",
        "reverted_count": reverted_count,
    }


@router.post("/recommend")
async def recommend_action(payload: RoutingRequest) -> dict[str, Any]:
    """Query current LinUCB policy for process routing action."""
    import numpy as np

    context = np.array(
        [
            min(1.0, payload.cpu_percent / 100.0),
            min(1.0, payload.memory_mb / 1024.0),
            min(1.0, payload.num_threads / 8.0),
            1.0 if payload.is_bursty else 0.0,
        ],
        dtype=float,
    )

    action, score = _bandit.select_action(context)
    core_type = "PERFORMANCE" if action == 1 else "EFFICIENCY"
    return {
        "action": action,
        "recommended_core_type": core_type,
        "ucb_score": round(score, 4),
        "explanation": f"Allocated to {core_type} core based on context features and UCB exploration score.",
    }
