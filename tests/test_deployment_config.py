from __future__ import annotations

import json
from pathlib import Path

from scripts.check_deployment_config import (
    check_frontend_assets,
    check_ignore_rules,
    check_runtime_templates,
    check_tracked_files_safety,
    check_vercel_json,
    run_all_checks,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_frontend_assets_present() -> None:
    errors = check_frontend_assets(REPO_ROOT)
    assert not errors, f"Frontend asset errors: {errors}"


def test_vercel_json_validity_and_headers() -> None:
    errors = check_vercel_json(REPO_ROOT)
    assert not errors, f"Vercel configuration errors: {errors}"

    # Additional assertions on vercel.json structure
    with open(REPO_ROOT / "vercel.json", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("outputDirectory") == "static"
    assert data.get("cleanUrls") is True

    # Check CSP directives
    csp_header = None
    for route in data.get("headers", []):
        for h in route.get("headers", []):
            if h.get("key") == "Content-Security-Policy":
                csp_header = h.get("value")

    assert csp_header is not None
    assert "'unsafe-eval'" not in csp_header
    assert "https://cdn.jsdelivr.net" in csp_header
    assert "https://fonts.googleapis.com" in csp_header
    assert "http://127.0.0.1:8000" in csp_header


def test_ignore_rules_contents() -> None:
    errors = check_ignore_rules(REPO_ROOT)
    assert not errors, f"Ignore rules errors: {errors}"

    # Verify .gitignore content
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore_text
    assert "!.env.example" in gitignore_text
    assert "pids.txt" in gitignore_text
    assert "bandit_stats.json" in gitignore_text

    # Verify .vercelignore content
    vercelignore_text = (REPO_ROOT / ".vercelignore").read_text(encoding="utf-8")
    assert "!static/" in vercelignore_text
    assert "/src/" in vercelignore_text
    assert "/tests/" in vercelignore_text
    assert "*.txt" not in [
        line.strip() for line in vercelignore_text.splitlines() if not line.startswith("#")
    ]


def test_tracked_files_do_not_contain_secrets() -> None:
    errors = check_tracked_files_safety(REPO_ROOT)
    assert not errors, f"Tracked file safety errors: {errors}"


def test_runtime_templates_exist() -> None:
    errors = check_runtime_templates(REPO_ROOT)
    assert not errors, f"Runtime template errors: {errors}"


def test_full_validation_run() -> None:
    assert run_all_checks(REPO_ROOT) is True
