"""
Integration tests for modern FastAPI routers, security headers, and scheduler controls.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from api.app import create_app


def test_api_health_endpoint() -> None:
    """Test health check probe."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


def test_api_hardware_topology() -> None:
    """Test hardware inspection endpoint returns valid core partitions."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/hardware/topology")
    assert response.status_code == 200
    data = response.json()
    assert data["total_logical_cores"] > 0
    assert "performance_cores" in data
    assert "efficiency_cores" in data


def test_api_live_telemetry() -> None:
    """Test live telemetry snapshot endpoint."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/telemetry/live")
    assert response.status_code == 200
    data = response.json()
    assert "total_cpu_percent" in data
    assert "estimated_power_watts" in data


def test_api_scheduler_recommend() -> None:
    """Test policy routing recommendation."""
    app = create_app()
    client = TestClient(app)
    payload = {
        "cpu_percent": 85.0,
        "memory_mb": 512.0,
        "num_threads": 4,
        "is_bursty": False,
    }
    response = client.post("/api/v1/scheduler/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] in (0, 1)
    assert data["recommended_core_type"] in ("PERFORMANCE", "EFFICIENCY")


def test_api_security_headers() -> None:
    """Verify presence of defensive HTTP headers on responses."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in headers


def test_api_scheduler_reset_auth(monkeypatch: os._Environ) -> None:
    """Test token enforcement on emergency reset endpoint."""
    app = create_app()
    client = TestClient(app)

    # 1. Without token configured: open access
    response = client.post("/api/v1/scheduler/reset")
    assert response.status_code == 200

    # 2. With token configured in environment
    monkeypatch.setenv("AIDAX_API_TOKEN", "super-secret-token")
    # Rejected without token
    unauth_resp = client.post("/api/v1/scheduler/reset")
    assert unauth_resp.status_code == 401

    # Rejected with invalid token
    bad_resp = client.post("/api/v1/scheduler/reset", headers={"X-API-Token": "wrong-token"})
    assert bad_resp.status_code == 401

    # Accepted with valid token
    good_resp = client.post("/api/v1/scheduler/reset", headers={"X-API-Token": "super-secret-token"})
    assert good_resp.status_code == 200
    assert good_resp.json()["status"] == "success"


def test_api_experiments_conditions() -> None:
    """Test retrieval of supported experiment baseline conditions."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/experiments/conditions")
    assert response.status_code == 200
    data = response.json()
    assert "linucb" in data["supported_conditions"]
    assert "thompson_sampling" in data["supported_conditions"]
    assert "cfs" in data["supported_conditions"]
