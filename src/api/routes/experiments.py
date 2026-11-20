"""
Experiment invocation and comparative evaluation endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from experiments.runner import ExperimentRunner
from hardware.detection import detect_cpu_topology

router = APIRouter(prefix="/api/v1/experiments", tags=["Experiments"])
_topology = detect_cpu_topology()
_runner = ExperimentRunner(topology=_topology)


class RunExperimentRequest(BaseModel):
    """Payload to trigger an experimental trial."""

    condition: str = Field(
        description="One of: cfs, static_p, static_e, round_robin, heuristic, linucb, thompson_sampling"
    )
    duration_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    trial_index: int = Field(default=0, ge=0)


@router.get("/conditions")
async def list_conditions() -> dict[str, Any]:
    """List all supported experimental scheduling conditions."""
    return {
        "supported_conditions": list(ExperimentRunner.SUPPORTED_CONDITIONS),
        "hardware_heterogeneous": _topology.is_heterogeneous,
    }


@router.post("/run")
async def run_experiment_trial(payload: RunExperimentRequest) -> dict[str, Any]:
    """Execute a single experimental evaluation trial under the chosen condition."""
    try:
        result = _runner.run_condition_trial(
            condition=payload.condition,
            trial_index=payload.trial_index,
            duration_seconds=payload.duration_seconds,
        )
        return {
            "condition": result.condition,
            "trial_index": result.trial_index,
            "duration_seconds": result.duration_seconds,
            "total_decisions": result.total_decisions,
            "average_cpu_percent": result.average_cpu_percent,
            "average_power_watts": result.average_power_watts,
            "jain_fairness_index": result.jain_fairness_index,
            "energy_delay_product": result.energy_delay_product,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
