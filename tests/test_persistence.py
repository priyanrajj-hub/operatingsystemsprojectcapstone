"""
Tests for persistence layer: async SQLAlchemy models, repositories, and checksummed checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from core.exceptions import CheckpointError
from persistence.checkpoints import CheckpointManager
from persistence.database import create_engine_and_sessionmaker, init_db
from persistence.repositories import (
    AuditRepository,
    DecisionRepository,
    ExperimentRepository,
    TelemetryRepository,
)
from scheduler.linucb import StableLinUCBBandit


@pytest.mark.asyncio
async def test_database_repositories_in_memory() -> None:
    """Test full repository lifecycle against in-memory async SQLite."""
    engine, sessionmaker = create_engine_and_sessionmaker("sqlite+aiosqlite:///:memory:")
    await init_db(engine)

    async with sessionmaker() as session:
        exp_repo = ExperimentRepository(session)
        dec_repo = DecisionRepository(session)
        tel_repo = TelemetryRepository(session)
        audit_repo = AuditRepository(session)

        # 1. Experiment lifecycle
        exp = await exp_repo.create("exp_test_01", "Integration Test Run", duration_seconds=30.0)
        assert exp.id == "exp_test_01"
        assert exp.status == "RUNNING"

        retrieved_exp = await exp_repo.get_by_id("exp_test_01")
        assert retrieved_exp is not None
        assert retrieved_exp.name == "Integration Test Run"

        # 2. Scheduling decision record
        dec = await dec_repo.record_decision(
            experiment_id="exp_test_01",
            pid=1234,
            process_name="worker_cpu",
            workload_type="CPU_INTENSIVE",
            core_allocated=0,
            core_type="PERFORMANCE",
            action_chosen=1,
            confidence_score=0.95,
            reward=0.88,
            exploration_bonus=0.15,
            execution_time_ms=1.2,
        )
        assert dec.id is not None
        assert dec.action_chosen == 1

        decisions = await dec_repo.get_decisions_for_experiment("exp_test_01")
        assert len(decisions) == 1
        assert decisions[0].pid == 1234

        # 3. Telemetry metric record
        metric = await tel_repo.record_telemetry(
            experiment_id="exp_test_01",
            total_cpu_percent=45.5,
            memory_percent=60.0,
            p_core_utilization=70.0,
            e_core_utilization=20.0,
            jain_fairness_index=0.92,
            estimated_power_watts=14.5,
        )
        assert metric.id is not None

        samples = await tel_repo.get_recent_samples("exp_test_01")
        assert len(samples) == 1
        assert samples[0].jain_fairness_index == 0.92

        # 4. Security audit record
        audit = await audit_repo.record_event(
            actor="admin",
            action="EMERGENCY_RESET",
            resource="affinity_mask",
            ip_address="127.0.0.1",
            status="SUCCESS",
            details={"reverted_pids": [1234]},
        )
        assert audit.id is not None

        logs = await audit_repo.list_recent(limit=10)
        assert len(logs) == 1
        assert logs[0].action == "EMERGENCY_RESET"

        # 5. Complete experiment
        await exp_repo.complete("exp_test_01")
        updated_exp = await exp_repo.get_by_id("exp_test_01")
        assert updated_exp is not None
        assert updated_exp.status == "COMPLETED"
        assert updated_exp.finished_at is not None

    await engine.dispose()


def test_checkpoint_atomic_save_and_load(tmp_path: Path) -> None:
    """Test checkpoint manager saves model and loads back with bit-exact parameters."""
    mgr = CheckpointManager(checkpoints_dir=str(tmp_path))
    bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.2, num_arms=2)

    # Perform sample update
    ctx = np.array([0.5, 0.2, 0.8, 0.1])
    bandit.update(action=1, context=ctx, reward=0.95)

    save_path = mgr.save_linucb(bandit, model_id="test_model_v1")
    assert Path(save_path).exists()

    # Load back
    loaded_bandit = mgr.load_linucb("test_model_v1")
    assert loaded_bandit.num_arms == bandit.num_arms
    assert loaded_bandit.context_dim == bandit.context_dim
    assert loaded_bandit.exploration_alpha == bandit.exploration_alpha
    assert loaded_bandit.total_decisions == 1
    np.testing.assert_allclose(loaded_bandit.arms[1].b, bandit.arms[1].b)
    np.testing.assert_allclose(loaded_bandit.arms[1].A, bandit.arms[1].A)


def test_checkpoint_tamper_detection(tmp_path: Path) -> None:
    """Test that modifying serialized state without updating checksum raises CheckpointError."""
    mgr = CheckpointManager(checkpoints_dir=str(tmp_path))
    bandit = StableLinUCBBandit(context_dim=4, exploration_alpha=1.0, num_arms=2)
    save_path = mgr.save_linucb(bandit, model_id="tampered_model")

    # Modify file contents directly
    with open(save_path, encoding="utf-8") as f:
        data = json.load(f)

    # Inject malicious change into payload
    data["payload"]["arms"][0]["b"] = [99999.0, 99999.0, 99999.0, 99999.0]
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Attempt to load tampered model
    with pytest.raises(CheckpointError, match="Checksum mismatch"):
        mgr.load_linucb("tampered_model")
