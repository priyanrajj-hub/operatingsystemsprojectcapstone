from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from aidax.api import app, get_system_health


def test_api_root_redirect() -> None:
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/static/index.html"


def test_api_live_and_history() -> None:
    client = TestClient(app)
    fake_rows = [
        {"timestamp": "100.0", "pid": "10", "action": "P-core"},
        {"timestamp": "101.0", "pid": "10", "action": "E-core"},
    ]

    with patch("aidax.api.read_csv_safe", return_value=fake_rows):
        res_live = client.get("/api/live")
        assert res_live.status_code == 200
        data_live = res_live.json()
        assert data_live["count"] == 1
        assert data_live["processes"][0]["action"] == "E-core"

        res_hist = client.get("/api/history?limit=10")
        assert res_hist.status_code == 200
        data_hist = res_hist.json()
        assert data_hist["count"] == 2


def test_api_bandit_stats() -> None:
    client = TestClient(app)
    fake_stats = {
        "total_decisions": 100,
        "heuristic_count": 20,
        "bandit_count": 80,
        "cumulative_regret": 15.2,
    }

    with patch("aidax.api.read_bandit_stats", return_value=fake_stats):
        response = client.get("/api/bandit-stats")
        assert response.status_code == 200
        data = response.json()
        assert data["heuristic_pct"] == 20.0
        assert data["bandit_pct"] == 80.0
        assert data["total_decisions"] == 100


def test_api_reset() -> None:
    client = TestClient(app)
    with patch("aidax.api.reset_all_affinities", return_value=4):
        response = client.post("/api/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["released_processes"] == 4


def test_api_aizen_offline_mode() -> None:
    client = TestClient(app)
    payload = {
        "cpu_percent_overall": 45.0,
        "memory_percent": 60.0,
        "total_decisions": 50,
        "regret": 2.5,
    }
    with patch("aidax.api.API_KEY", ""):
        response = client.post("/api/aizen", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "Aizen Offline" in data["health"]


def test_get_system_health() -> None:
    health = get_system_health()
    assert "cpu_percent_overall" in health
    assert "memory_percent" in health
    assert "cpu_count_logical" in health
    assert isinstance(health["memory_percent"], (int, float))


def test_api_health_and_system_endpoints() -> None:
    client = TestClient(app)
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_system = client.get("/api/system")
    assert res_system.status_code == 200
    assert "cpu_percent_overall" in res_system.json()

    res_status = client.get("/api/scheduler/status")
    assert res_status.status_code == 200
    assert "status" in res_status.json()

    res_stats = client.get("/api/scheduler/stats")
    assert res_stats.status_code == 200

    res_procs = client.get("/api/processes")
    assert res_procs.status_code == 200
    assert "processes" in res_procs.json()


def test_api_hardware_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/hardware")
    assert res.status_code == 200
    data = res.json()
    assert "total_logical_cores" in data
    assert "is_heterogeneous" in data
    assert "p_cores" in data
    assert "e_cores" in data


def test_api_telemetry_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert "system" in data
    assert "bandit" in data
    assert "timestamp" in data


def test_api_scheduler_lifecycle() -> None:
    client = TestClient(app)
    res_start = client.post("/api/scheduler/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "running"

    res_stop = client.post("/api/scheduler/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "idle"


def test_api_process_affinity_control(tmp_path: Path) -> None:
    import json
    import os
    from unittest.mock import patch

    client = TestClient(app)

    # 1. Non-existent PID returns 404
    res_404 = client.post("/api/process/999999/affinity", json={"cores": [0]})
    assert res_404.status_code == 404

    # 2. Existing PID not in PID_FILE returns 403 (defense against confused deputy)
    current_pid = os.getpid()
    with patch("aidax.api.PID_FILE", str(tmp_path / "nonexistent_pids.txt")):
        res_403 = client.post(f"/api/process/{current_pid}/affinity", json={"cores": [0]})
        assert res_403.status_code == 403

    # 3. Tracked PID in PID_FILE succeeds
    fake_pid_file = tmp_path / "pids.txt"
    fake_pid_file.write_text(
        json.dumps({"pid": current_pid, "type": "heavy"}) + "\n", encoding="utf-8"
    )
    with (
        patch("aidax.api.PID_FILE", str(fake_pid_file)),
        patch("process.affinity.set_process_affinity", return_value=True),
    ):
        res_ok = client.post(f"/api/process/{current_pid}/affinity", json={"cores": [0, 1]})
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "success"
