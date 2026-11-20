from __future__ import annotations

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
