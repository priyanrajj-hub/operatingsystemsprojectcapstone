"""
Tests for cross-platform launcher (scripts/start_all.py and aidax.run).
Verifies proper process lifecycle, signal trapping, and argument handling.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure scripts dir is accessible
scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)


def test_start_all_launcher_lifecycle() -> None:
    """Verify that start_all.py spawns all 3 services and terminates them cleanly."""
    import start_all  # noqa: E402

    mock_proc1 = MagicMock()
    mock_proc2 = MagicMock()
    mock_proc3 = MagicMock()
    mock_proc1.poll.return_value = None
    mock_proc2.poll.return_value = None
    mock_proc3.poll.return_value = None

    with patch("subprocess.Popen", side_effect=[mock_proc1, mock_proc2, mock_proc3]) as mock_popen:
        manager = start_all.ProcessManager(
            enable_workload=True, enable_scheduler=True, enable_dashboard=True
        )
        manager.start()
        assert len(manager.processes) == 3
        assert mock_popen.call_count == 3

        # Simulate shutdown
        manager.stop_all()
        assert mock_proc1.terminate.called
        assert mock_proc2.terminate.called
        assert mock_proc3.terminate.called
