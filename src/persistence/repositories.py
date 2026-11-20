"""
Repository implementations for AI-DAX database access.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import (
    AuditLog,
    Experiment,
    SchedulingDecision,
    TelemetryMetric,
)

logger = logging.getLogger("aidax.persistence.repositories")


class ExperimentRepository:
    """Manages experiment persistence and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        experiment_id: str,
        name: str,
        description: str | None = None,
        duration_seconds: float = 60.0,
        num_trials: int = 1,
    ) -> Experiment:
        """Create and persist a new experiment record."""
        exp = Experiment(
            id=experiment_id,
            name=name,
            description=description,
            duration_seconds=duration_seconds,
            num_trials=num_trials,
            status="RUNNING",
            created_at=time.time(),
        )
        self.session.add(exp)
        await self.session.flush()
        return exp

    async def get_by_id(self, experiment_id: str) -> Experiment | None:
        """Retrieve an experiment by its primary ID."""
        result = await self.session.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        return result.scalars().first()

    async def complete(self, experiment_id: str, status: str = "COMPLETED") -> None:
        """Mark an experiment as completed with a completion timestamp."""
        exp = await self.get_by_id(experiment_id)
        if exp:
            exp.status = status
            exp.finished_at = time.time()
            await self.session.flush()

    async def list_recent(self, limit: int = 20) -> list[Experiment]:
        """List recent experiments ordered descending by creation timestamp."""
        result = await self.session.execute(
            select(Experiment).order_by(desc(Experiment.created_at)).limit(limit)
        )
        return list(result.scalars().all())


class DecisionRepository:
    """Records and queries scheduling decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_decision(
        self,
        experiment_id: str,
        pid: int,
        process_name: str,
        workload_type: str,
        core_allocated: int,
        core_type: str,
        action_chosen: int,
        confidence_score: float,
        reward: float | None = None,
        exploration_bonus: float = 0.0,
        execution_time_ms: float = 0.0,
    ) -> SchedulingDecision:
        """Persist a single scheduling decision."""
        decision = SchedulingDecision(
            experiment_id=experiment_id,
            timestamp=time.time(),
            pid=pid,
            process_name=process_name,
            workload_type=workload_type,
            core_allocated=core_allocated,
            core_type=core_type,
            action_chosen=action_chosen,
            confidence_score=confidence_score,
            reward=reward,
            exploration_bonus=exploration_bonus,
            execution_time_ms=execution_time_ms,
        )
        self.session.add(decision)
        await self.session.flush()
        return decision

    async def get_decisions_for_experiment(
        self, experiment_id: str, limit: int = 1000
    ) -> list[SchedulingDecision]:
        """Retrieve decisions for an experiment in chronological order."""
        result = await self.session.execute(
            select(SchedulingDecision)
            .where(SchedulingDecision.experiment_id == experiment_id)
            .order_by(SchedulingDecision.timestamp)
            .limit(limit)
        )
        return list(result.scalars().all())


class TelemetryRepository:
    """Records and queries aggregate hardware telemetry samples."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_telemetry(
        self,
        experiment_id: str,
        total_cpu_percent: float,
        memory_percent: float,
        p_core_utilization: float,
        e_core_utilization: float,
        jain_fairness_index: float,
        estimated_power_watts: float,
    ) -> TelemetryMetric:
        """Persist aggregate telemetry metrics."""
        sample = TelemetryMetric(
            experiment_id=experiment_id,
            timestamp=time.time(),
            total_cpu_percent=total_cpu_percent,
            memory_percent=memory_percent,
            p_core_utilization=p_core_utilization,
            e_core_utilization=e_core_utilization,
            jain_fairness_index=jain_fairness_index,
            estimated_power_watts=estimated_power_watts,
        )
        self.session.add(sample)
        await self.session.flush()
        return sample

    async def get_recent_samples(
        self, experiment_id: str | None = None, limit: int = 100
    ) -> list[TelemetryMetric]:
        """Retrieve recent telemetry samples ordered chronologically."""
        stmt = select(TelemetryMetric).order_by(desc(TelemetryMetric.timestamp)).limit(limit)
        if experiment_id:
            stmt = stmt.where(TelemetryMetric.experiment_id == experiment_id)
        result = await self.session.execute(stmt)
        samples = list(result.scalars().all())
        samples.reverse()
        return samples


class AuditRepository:
    """Persists and queries security audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        actor: str,
        action: str,
        resource: str,
        ip_address: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Persist a security audit log record."""
        details_json = json.dumps(details or {})
        entry = AuditLog(
            timestamp=time.time(),
            actor=actor,
            action=action,
            resource=resource,
            ip_address=ip_address,
            status=status,
            details_json=details_json,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_recent(self, limit: int = 100) -> list[AuditLog]:
        """Retrieve recent security audit logs."""
        result = await self.session.execute(
            select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
        )
        return list(result.scalars().all())
