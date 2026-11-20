"""
Unit tests for security, environment configuration, and API proxy defenses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aidax.api import _ai_request_log, app
from core.config import ConfigurationError, Settings, mask_secret, validate_settings

# Allow importing from scripts directory
scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
from gen_secret import generate_secret  # noqa: E402


def test_mask_secret() -> None:
    assert mask_secret(None) == "<unset>"
    assert mask_secret("") == "<unset>"
    assert mask_secret("short") == "******"
    masked = mask_secret("AIzaSyVeryLongSecretKey12345")
    assert masked.startswith("AIza...")
    assert "len=28" in masked
    assert "VeryLongSecretKey" not in masked


def test_settings_repr_masks_secrets() -> None:
    cfg = Settings(
        api_token="super-secret-auth-token-12345",
        gemini_api_key="AIzaSyConfidentialKeyString9876",
    )
    rep = repr(cfg)
    assert "super-secret" not in rep
    assert "ConfidentialKeyString" not in rep
    assert "supe..." in rep
    assert "AIza..." in rep


def test_validate_settings_errors() -> None:
    # Invalid port
    with pytest.raises(ConfigurationError, match="AIDAX_PORT"):
        validate_settings(Settings(port=99999))

    # Invalid alpha reward
    with pytest.raises(ConfigurationError, match="alpha_reward"):
        validate_settings(Settings(alpha_reward=1.5))

    # Invalid rate limit
    with pytest.raises(ConfigurationError, match="AIDAX_RATE_LIMIT_PER_MINUTE"):
        validate_settings(Settings(rate_limit_per_minute=0))


def test_gen_secret_utility() -> None:
    tok1 = generate_secret(32, format_type="hex")
    tok2 = generate_secret(32, format_type="hex")
    assert len(tok1) == 64
    assert tok1 != tok2

    urlsafe_tok = generate_secret(48, format_type="urlsafe")
    assert len(urlsafe_tok) >= 64
    assert isinstance(urlsafe_tok, str)


def test_api_aizen_rate_limiting() -> None:
    client = TestClient(app)
    payload = {
        "cpu_percent_overall": 45.0,
        "memory_percent": 60.0,
        "total_decisions": 50,
        "regret": 2.5,
    }
    # Clear rate limit state for client test
    _ai_request_log.clear()

    from unittest.mock import patch

    with patch("aidax.api.API_KEY", ""):
        # Make 10 allowed requests
        for _ in range(10):
            res = client.post("/api/aizen", json=payload)
            assert res.status_code == 200

        # 11th request should be rate-limited
        res_limited = client.post("/api/aizen", json=payload)
        assert res_limited.status_code == 429
        assert res_limited.json()["health"] == "Rate Limit Exceeded"


def test_api_jarvis_rate_limiting_and_offline() -> None:
    client = TestClient(app)
    payload = {
        "cpu_percent_overall": 30.0,
        "memory_percent": 50.0,
        "total_decisions": 10,
        "regret": 1.0,
        "voice_query": "Hello governor",
        "language": "English",
    }
    _ai_request_log.clear()
    from unittest.mock import patch

    with patch("aidax.api.API_KEY", ""):
        for _ in range(10):
            res = client.post("/api/jarvis", json=payload)
            assert res.status_code == 200
        res_limited = client.post("/api/jarvis", json=payload)
        assert res_limited.status_code == 429


def test_api_payload_validation_bounds() -> None:
    client = TestClient(app)
    # CPU over 100% should fail validation
    invalid_payload = {
        "cpu_percent_overall": 150.0,
        "memory_percent": 60.0,
        "total_decisions": 50,
        "regret": 2.5,
    }
    res = client.post("/api/aizen", json=invalid_payload)
    assert res.status_code == 422  # Pydantic unprocessable entity
