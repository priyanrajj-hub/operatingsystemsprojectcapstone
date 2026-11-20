#!/usr/bin/env python3
"""
Safe Secret Scanner.
Audits current files and full git history for exposed credentials, tokens, and keys.
STRICT COMPLIANCE: NEVER prints or logs raw secrets. Outputs only masked representations (e.g., AIza****).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    ("Google / Gemini API Key (AIza)", re.compile(r"(AIza[0-9A-Za-z-_]{35})")),
    ("Google / Gemini API Key (AQ)", re.compile(r"(AQ\.[0-9A-Za-z-_]{30,})")),
    ("OpenAI API Key", re.compile(r"(sk-[A-Za-z0-9-_]{20,})")),
    ("GitHub Personal Access Token", re.compile(r"(ghp_[A-Za-z0-9]{36})")),
    (
        "GitHub OAuth / App Token",
        re.compile(r"(gho_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36})"),
    ),
    ("Vercel Token / Project ID", re.compile(r"(vercel_[A-Za-z0-9-_]{20,})")),
    (
        "Vercel OIDC / JWT Token",
        re.compile(r"(eyJ[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,})"),
    ),
    ("Generic Bearer Token", re.compile(r"[bB]earer\s+['\"]?([A-Za-z0-9-_\.]{16,})")),
    (
        "Generic Secret Assignment",
        re.compile(
            r"(?:api_key|apikey|secret|token|password|auth_token)\s*[:=]\s*['\"]?([^'\"\s\r\n]{8,})['\"]?",
            re.IGNORECASE,
        ),
    ),
]


def mask_secret(secret_val: str) -> str:
    """Mask secret value showing only first 4 chars followed by asterisks."""
    if len(secret_val) <= 4:
        return "****"
    return secret_val[:4] + "****"


def scan_text_for_secrets(text: str, filename: str) -> list[dict[str, Any]]:
    """Scan text content and return masked findings."""
    findings = []
    lines = text.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        for secret_type, regex in SECRET_PATTERNS:
            for match in regex.finditer(line):
                val = match.group(1)
                # Ignore placeholders like 'your-key-here', 'change-me'
                if any(
                    p in val.lower()
                    for p in ["your-key", "change-me", "fake-token", "placeholder", "xxx"]
                ):
                    continue
                findings.append(
                    {
                        "file": filename,
                        "line": line_idx,
                        "type": secret_type,
                        "masked": mask_secret(val),
                        "length": len(val),
                    }
                )
    return findings


def scan_workspace_files(root_dir: Path) -> list[dict[str, Any]]:
    """Scan all current workspace files, excluding .venv and .git."""
    all_findings = []
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        # Skip virtual env and git internal objects
        parts = path.parts
        if ".venv" in parts or ".git" in parts or "__pycache__" in parts:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            rel_path = str(path.relative_to(root_dir)).replace("\\", "/")
            findings = scan_text_for_secrets(content, rel_path)
            all_findings.extend(findings)
        except Exception:
            pass
    return all_findings


def scan_git_history(root_dir: Path) -> list[dict[str, Any]]:
    """Scan full git history diffs."""
    all_findings = []
    try:
        res = subprocess.run(
            ["git", "log", "-p", "--all"],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        diff_text = res.stdout
        current_commit = "UNKNOWN"
        current_file = "UNKNOWN"

        for line in diff_text.splitlines():
            if line.startswith("commit "):
                current_commit = line.split()[1][:8]
            elif line.startswith("+++ b/"):
                current_file = line[6:].strip()
            elif line.startswith("+") and not line.startswith("+++"):
                added_line = line[1:]
                for secret_type, regex in SECRET_PATTERNS:
                    for match in regex.finditer(added_line):
                        val = match.group(1)
                        if any(
                            p in val.lower()
                            for p in ["your-key", "change-me", "fake-token", "placeholder", "xxx"]
                        ):
                            continue
                        all_findings.append(
                            {
                                "commit": current_commit,
                                "file": current_file,
                                "type": secret_type,
                                "masked": mask_secret(val),
                                "length": len(val),
                            }
                        )
    except Exception as e:
        print(f"Error scanning git history: {e}")
    return all_findings


def main() -> None:
    root = Path(".")
    print("Scanning workspace files...")
    workspace_findings = scan_workspace_files(root)

    print("Scanning git commit history...")
    history_findings = scan_git_history(root)

    out_dir = Path("docs/security/scan-output")
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "workspace_findings": workspace_findings,
        "history_findings": history_findings,
    }

    report_path = out_dir / "secret_scan_summary.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(
        f"Scan complete. Workspace hits: {len(workspace_findings)}, History hits: {len(history_findings)}"
    )
    print(f"Masked report saved safely to {report_path}")


if __name__ == "__main__":
    main()
