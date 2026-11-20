#!/usr/bin/env python3
"""
Automated deployment configuration and security validator for AI-DAX Lite.
Verifies Vercel deployment manifests, ignore rules, frontend assets, and secret protections.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def check_frontend_assets(root: Path) -> list[str]:
    """Verify required frontend assets exist and are non-empty."""
    errors = []
    static_dir = root / "static"
    if not static_dir.is_dir():
        errors.append("static directory is missing")
        return errors

    required_files = ["index.html", "app.js", "style.css"]
    for filename in required_files:
        p = static_dir / filename
        if not p.is_file():
            errors.append(f"Required frontend asset static/{filename} is missing")
        elif p.stat().st_size == 0:
            errors.append(f"Required frontend asset static/{filename} is empty")

    return errors


def check_vercel_json(root: Path) -> list[str]:
    """Audit vercel.json structure, output directory, and CSP directives."""
    errors = []
    vercel_path = root / "vercel.json"
    if not vercel_path.is_file():
        errors.append("vercel.json is missing")
        return errors

    try:
        with open(vercel_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"vercel.json is invalid JSON: {e}"]

    # 1. Output directory
    out_dir = data.get("outputDirectory")
    if not out_dir:
        errors.append("vercel.json is missing 'outputDirectory'")
    elif not (root / out_dir).is_dir():
        errors.append(f"vercel.json outputDirectory '{out_dir}' does not exist on disk")

    # 2. Version
    if data.get("version") != 2:
        errors.append("vercel.json must specify 'version': 2")

    # 3. Security headers & CSP
    headers_config = data.get("headers", [])
    if not headers_config:
        errors.append("vercel.json has no security headers configured")
    else:
        all_header_keys = set()
        csp_value = ""
        for route_header in headers_config:
            for h in route_header.get("headers", []):
                key = h.get("key", "")
                all_header_keys.add(key)
                if key == "Content-Security-Policy":
                    csp_value = h.get("value", "")

        for required_header in [
            "Content-Security-Policy",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
        ]:
            if required_header not in all_header_keys:
                errors.append(f"Missing recommended security header: {required_header}")

        if csp_value:
            if "'unsafe-eval'" in csp_value:
                errors.append("CSP contains dangerous directive 'unsafe-eval'")
            if "default-src 'self'" not in csp_value:
                errors.append("CSP must specify default-src 'self'")
            if "cdn.jsdelivr.net" not in csp_value:
                errors.append("CSP missing cdn.jsdelivr.net for Chart.js")
            if "fonts.googleapis.com" not in csp_value:
                errors.append("CSP missing fonts.googleapis.com for Google Fonts")

    return errors


def check_ignore_rules(root: Path) -> list[str]:
    """Verify .gitignore and .vercelignore rules adhere to security and deployment constraints."""
    errors = []

    # 1. .gitignore
    gitignore_path = root / ".gitignore"
    if not gitignore_path.is_file():
        errors.append(".gitignore is missing")
    else:
        text = gitignore_path.read_text(encoding="utf-8")
        for expected in [".env", ".venv/", "__pycache__/", "pids.txt", "bandit_stats.json"]:
            if expected not in text:
                errors.append(f".gitignore is missing critical pattern: '{expected}'")
        if "!.env.example" not in text:
            errors.append(".gitignore must explicitly preserve '!.env.example'")

    # 2. .vercelignore
    vercelignore_path = root / ".vercelignore"
    if not vercelignore_path.is_file():
        errors.append(".vercelignore is missing")
    else:
        vtext = vercelignore_path.read_text(encoding="utf-8")
        for excluded_dir in ["src/", "api/", "tests/", "docs/"]:
            if excluded_dir not in vtext:
                errors.append(f".vercelignore must exclude backend directory: '{excluded_dir}'")

        # Check for broad problematic top-level wildcards
        lines = [
            line.strip() for line in vtext.splitlines() if line.strip() and not line.startswith("#")
        ]
        if "*.txt" in lines:
            errors.append(
                ".vercelignore contains overly broad '*.txt' which may hide static assets"
            )
        if "*.md" in lines:
            errors.append(".vercelignore contains overly broad '*.md' which may hide static assets")

        # Check static preservation
        if "!static/" not in vtext and "!static/**" not in vtext:
            errors.append(".vercelignore must explicitly preserve static/ assets")

    return errors


def check_tracked_files_safety(root: Path) -> list[str]:
    """Ensure no secrets or dynamic runtime telemetry are tracked by Git."""
    errors = []
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        tracked = set(proc.stdout.splitlines())
    except Exception as e:
        return [f"Unable to execute git ls-files: {e}"]

    sensitive_exact = {".env", ".env.local", "pids.txt", "bandit_stats.json", "scheduler_log.csv"}
    for f in tracked:
        if f in sensitive_exact:
            errors.append(f"Security violation: generated/sensitive file is tracked by Git: '{f}'")
        if f.endswith((".pem", ".key", ".cert", ".pfx", ".p12")) and not f.startswith("tests/"):
            errors.append(f"Security violation: private key/cert is tracked by Git: '{f}'")

    return errors


def check_runtime_templates(root: Path) -> list[str]:
    """Verify required runtime configuration templates exist."""
    errors = []
    env_example = root / ".env.example"
    if not env_example.is_file() or env_example.stat().st_size == 0:
        errors.append("Tracked template .env.example is missing or empty")

    stats_example = root / "config" / "bandit_stats.example.json"
    if not stats_example.is_file():
        errors.append("Tracked template config/bandit_stats.example.json is missing")
    else:
        try:
            with open(stats_example, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            errors.append(f"config/bandit_stats.example.json is invalid JSON: {e}")

    return errors


def run_all_checks(root: Path | None = None) -> bool:
    """Execute all validation checks and print clear diagnostics."""
    if root is None:
        root = Path(__file__).resolve().parent.parent

    print(f"Running AI-DAX Deployment Configuration Audit on: {root}")
    all_errors: list[str] = []

    checks = [
        ("Frontend Assets", check_frontend_assets),
        ("Vercel Configuration", check_vercel_json),
        ("Ignore Rules (.gitignore & .vercelignore)", check_ignore_rules),
        ("Git Tracked Files & Secret Safety", check_tracked_files_safety),
        ("Runtime Config Templates", check_runtime_templates),
    ]

    for name, check_fn in checks:
        print(f"  [CHECKING] {name}...", end=" ")
        errs = check_fn(root)
        if errs:
            print("FAILED")
            for err in errs:
                print(f"    - ERROR: {err}")
            all_errors.extend(errs)
        else:
            print("PASSED")

    if all_errors:
        print(f"\nAudit completed with {len(all_errors)} error(s).")
        return False

    print("\nAll deployment and configuration checks PASSED successfully.")
    return True


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
