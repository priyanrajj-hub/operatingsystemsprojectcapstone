"""
Persistence module for AI-DAX database models, repositories, and verified checkpoints.
"""

from persistence.checkpoints import CheckpointManager
from persistence.database import DatabaseManager, create_engine_and_sessionmaker, init_db
from persistence.models import (
    AuditLog,
    Base,
    Experiment,
    ModelCheckpoint,
    SchedulingDecision,
    TelemetryMetric,
)
from persistence.repositories import (
    AuditRepository,
    DecisionRepository,
    ExperimentRepository,
    TelemetryRepository,
)

__all__ = [
    "AuditLog",
    "AuditRepository",
    "Base",
    "CheckpointManager",
    "DatabaseManager",
    "DecisionRepository",
    "Experiment",
    "ExperimentRepository",
    "ModelCheckpoint",
    "SchedulingDecision",
    "TelemetryMetric",
    "TelemetryRepository",
    "create_engine_and_sessionmaker",
    "init_db",
]
