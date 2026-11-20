from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from aidax.scheduler import AIScheduler, SchedulerConfig


def test_reward_computation() -> None:
    config = SchedulerConfig(
        alpha_reward=0.7,
        beta_reward=0.3,
        p_core_energy_cost=1.0,
        e_core_energy_cost=0.3,
        invol_ctx_norm_divisor=1000.0,
    )
    scheduler = AIScheduler(config=config)

    # Action 0 (P-core) with 500 invol ctx switches/sec
    # norm_invol = 500 / 1000 = 0.5
    # energy_proxy = 1.0
    # reward = -(0.7 * 0.5 + 0.3 * 1.0) = -(0.35 + 0.3) = -0.65
    r0 = scheduler._compute_reward(action=0, invol_ctx_rate=500.0)
    assert np.isclose(r0, -0.65)

    # Action 1 (E-core) with 2000 invol ctx switches/sec (clamped to 1.0)
    # norm_invol = min(2000 / 1000, 1.0) = 1.0
    # energy_proxy = 0.3
    # reward = -(0.7 * 1.0 + 0.3 * 0.3) = -(0.7 + 0.09) = -0.79
    r1 = scheduler._compute_reward(action=1, invol_ctx_rate=2000.0)
    assert np.isclose(r1, -0.79)


def test_core_detection_fallback() -> None:
    scheduler = AIScheduler()
    p_cores, e_cores = scheduler.detect_cores()
    assert len(p_cores) > 0
    assert len(e_cores) > 0
    assert set(p_cores).isdisjoint(set(e_cores))


def test_pid_reuse_guard(tmp_path: Path) -> None:
    pid_file = tmp_path / "pids.txt"
    scheduler = AIScheduler(pid_file=str(pid_file))

    # Mock process: PID 101, valid create_time 1000.0
    mock_proc = MagicMock()
    mock_proc.create_time.return_value = 1000.0
    mock_proc.username.return_value = "test_user"

    with patch("psutil.Process", return_value=mock_proc):
        # Case 1: Matching PID and create_time -> accepted
        valid_entry = {"pid": 101, "type": "Heavy", "start_time": 1000.0}
        pid_file.write_text(json.dumps(valid_entry) + "\n", encoding="utf-8")
        active = scheduler.get_active_pids()
        assert len(active) == 1
        assert active[0] == (101, "Heavy")

        # Case 2: Recycled PID (start_time mismatch) -> rejected
        recycled_entry = {"pid": 101, "type": "Heavy", "start_time": 500.0}
        pid_file.write_text(json.dumps(recycled_entry) + "\n", encoding="utf-8")
        active_recycled = scheduler.get_active_pids()
        assert len(active_recycled) == 0


def test_atomic_stats_and_csv_write(tmp_path: Path) -> None:
    stats_file = tmp_path / "bandit_stats.json"
    log_file = tmp_path / "scheduler_log.csv"
    scheduler = AIScheduler(stats_file=str(stats_file), log_file=str(log_file))
    scheduler.heuristic_count = 5
    scheduler.bandit_count = 10
    scheduler.cumulative_regret = 1.234

    scheduler._write_bandit_stats()
    assert stats_file.exists()

    with open(stats_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["heuristic_count"] == 5
    assert data["bandit_count"] == 10
    assert np.isclose(data["cumulative_regret"], 1.234)

    # Test CSV write
    test_rows = [
        "100.0,1,Heavy,P-core,\"[0, 1]\",heuristic,50.0,10.0,5.0,1.0,0.0,0.0,0.0,0.0,0.7,0.3\n"
    ]
    scheduler._write_csv_rows(test_rows)
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert content.startswith("timestamp,pid,true_type")
    assert "Heavy" in content


def test_run_cycle_heuristic_and_bandit(tmp_path: Path) -> None:
    pid_file = tmp_path / "pids.txt"
    log_file = tmp_path / "log.csv"
    stats_file = tmp_path / "stats.json"

    config = SchedulerConfig(
        cold_start_threshold=1,
        pid_file=str(pid_file),
        log_file=str(log_file),
        stats_file=str(stats_file),
    )
    scheduler = AIScheduler(config=config)

    mock_proc = MagicMock()
    mock_proc.create_time.return_value = 100.0
    mock_proc.username.return_value = "user"
    mock_proc.cpu_percent.return_value = 65.0
    ctx_mock = MagicMock()
    ctx_mock.voluntary = 10
    ctx_mock.involuntary = 5
    mock_proc.num_ctx_switches.return_value = ctx_mock
    mock_proc.cpu_affinity.return_value = [0]

    with patch("psutil.Process", return_value=mock_proc):
        pid_file.write_text(
            json.dumps({"pid": 42, "type": "Heavy", "start_time": 100.0}) + "\n",
            encoding="utf-8",
        )

        # Cycle 1: Initialization / priming
        rows1 = scheduler.run_cycle()
        assert len(rows1) == 0
        assert 42 in scheduler.history

        # Cycle 2: First decision -> cold-start heuristic
        ctx_mock.voluntary = 20
        ctx_mock.involuntary = 15
        rows2 = scheduler.run_cycle()
        assert len(rows2) == 1
        assert "heuristic" in rows2[0]
        assert scheduler.heuristic_count == 1

        # Cycle 3: Second decision -> exceeds cold-start threshold (1), so bandit takes over
        ctx_mock.voluntary = 30
        ctx_mock.involuntary = 25
        rows3 = scheduler.run_cycle()
        assert len(rows3) == 1
        assert "bandit" in rows3[0]
        assert scheduler.bandit_count == 1


def test_reset_affinities(tmp_path: Path) -> None:
    pid_file = tmp_path / "pids.txt"
    scheduler = AIScheduler(pid_file=str(pid_file))

    mock_proc = MagicMock()
    mock_proc.create_time.return_value = 100.0
    mock_proc.username.return_value = "user"

    with patch("psutil.Process", return_value=mock_proc):
        pid_file.write_text(
            json.dumps({"pid": 99, "type": "Light", "start_time": 100.0}) + "\n",
            encoding="utf-8",
        )
        scheduler.reset_affinities()
        assert mock_proc.cpu_affinity.called
