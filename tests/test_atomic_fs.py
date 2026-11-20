"""
Unit tests for atomic file system operations and zero tempfile leakage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.fs import atomic_replace, atomic_write_json, atomic_write_text


def test_atomic_write_text_success(tmp_path: Path) -> None:
    target = tmp_path / "test.txt"
    atomic_write_text(target, "Hello Atomic World")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Hello Atomic World"
    # Verify no temp files left behind
    assert len(list(tmp_path.glob(".*.tmp"))) == 0


def test_atomic_write_json_success(tmp_path: Path) -> None:
    target = tmp_path / "stats.json"
    data = {"metric": 42, "status": "ok"}
    atomic_write_json(target, data, indent=2)
    assert target.exists()
    import json

    assert json.loads(target.read_text(encoding="utf-8")) == data
    assert len(list(tmp_path.glob(".*.tmp"))) == 0


def test_atomic_write_cleanup_on_failure(tmp_path: Path) -> None:
    """Verify that if an exception occurs mid-write or in replace, tempfile is cleaned up."""
    target = tmp_path / "fail.json"

    with patch("os.replace", side_effect=OSError("Disk Full Simulation")):
        with pytest.raises(OSError, match="Disk Full Simulation"):
            atomic_write_text(target, "Will fail")

    # Target should not exist and zero temp files must remain
    assert not target.exists()
    assert len(list(tmp_path.glob(".*.tmp"))) == 0


def test_atomic_replace_permission_error_retry(tmp_path: Path) -> None:
    """Verify exponential backoff retry on Windows PermissionError."""
    import os

    real_os_replace = os.replace

    target = tmp_path / "locked.txt"
    target.write_text("initial", encoding="utf-8")
    temp = tmp_path / "temp.tmp"
    temp.write_text("updated", encoding="utf-8")

    call_count = 0

    def mock_replace(src: Path | str, dst: Path | str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise PermissionError("[WinError 32] The process cannot access the file")
        real_os_replace(src, dst)

    with patch("os.replace", side_effect=mock_replace):
        atomic_replace(temp, target, max_retries=5, backoff_base=0.01)

    assert call_count == 3
    assert target.read_text(encoding="utf-8") == "updated"
    assert not temp.exists()
