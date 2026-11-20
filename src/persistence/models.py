"""
SQLAlchemy ORM models for AI-DAX persistent telemetry, decisions, and checkpoints.
"""

from __future__ import annotations

import time

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all AI-DAX persistence models."""


class Experiment(Base):
    """Represents a scheduled scheduling evaluation experiment run."""

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=60.0)
    num_trials: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    finished_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    decisions: Mapped[list[SchedulingDecision]] = relationship(
        "SchedulingDecision", back_populates="experiment", cascade="all, delete-orphan"
    )
    telemetry: Mapped[list[TelemetryMetric]] = relationship(
        "TelemetryMetric", back_populates="experiment", cascade="all, delete-orphan"
    )


class SchedulingDecision(Base):
    """Records an individual process scheduling decision made by an agent or baseline."""

    __tablename__ = "scheduling_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(64), ForeignKey("experiments.id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    pid: Mapped[int] = mapped_column(Integer, index=True)
    process_name: Mapped[str] = mapped_column(String(64), default="")
    workload_type: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    core_allocated: Mapped[int] = mapped_column(Integer)
    core_type: Mapped[str] = mapped_column(String(16))  # PERFORMANCE / EFFICIENCY
    action_chosen: Mapped[int] = mapped_column(Integer)  # 0: E-core, 1: P-core
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    exploration_bonus: Mapped[float] = mapped_column(Float, default=0.0)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)

    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="decisions")


class TelemetryMetric(Base):
    """Aggregate hardware and system telemetry sampled during scheduling cycles."""

    __tablename__ = "telemetry_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(64), ForeignKey("experiments.id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    total_cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    p_core_utilization: Mapped[float] = mapped_column(Float, default=0.0)
    e_core_utilization: Mapped[float] = mapped_column(Float, default=0.0)
    jain_fairness_index: Mapped[float] = mapped_column(Float, default=1.0)
    estimated_power_watts: Mapped[float] = mapped_column(Float, default=0.0)

    experiment: Mapped[Experiment] = relationship("Experiment", back_populates="telemetry")


class ModelCheckpoint(Base):
    """Stores serialized contextual bandit or RL policy weights with cryptographic verification."""

    __tablename__ = "model_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    alpha: Mapped[float] = mapped_column(Float, default=1.0)
    num_features: Mapped[int] = mapped_column(Integer, default=4)
    arms_count: Mapped[int] = mapped_column(Integer, default=2)
    parameters_json: Mapped[str] = mapped_column(Text)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class AuditLog(Base):
    """Persistent security audit log recording administrative, process, and API operations."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(128))
    ip_address: Mapped[str] = mapped_column(String(45))
    status: Mapped[str] = mapped_column(String(16))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
