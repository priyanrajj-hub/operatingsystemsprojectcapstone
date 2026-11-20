"""
Unit tests for platform guards and Linux/Windows CPU topology detection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

from hardware.detection import detect_cpu_topology
from hardware.linux import detect_linux_topology, parse_cpulist
from process.affinity import set_process_affinity


def test_parse_cpulist() -> None:
    assert parse_cpulist("0-3,8,10-12") == [0, 1, 2, 3, 8, 10, 11, 12]
    assert parse_cpulist("0-15") == list(range(16))
    assert parse_cpulist("16-23") == list(range(16, 24))
    assert parse_cpulist("") == []


def test_linux_cpu_core_atom_sysfs_mock() -> None:
    """Verify detection via /sys/devices/cpu_core/cpus and /sys/devices/cpu_atom/cpus."""
    def fake_exists(path: str) -> bool:
        if path in (
            "/sys/devices/cpu_core/cpus",
            "/sys/devices/cpu_atom/cpus",
            "/sys/devices/system/cpu",
        ):
            return True
        return False

    def fake_open(path: str, *args, **kwargs):
        if path == "/sys/devices/cpu_core/cpus":
            return mock_open(read_data="0-15\n")()
        elif path == "/sys/devices/cpu_atom/cpus":
            return mock_open(read_data="16-23\n")()
        return mock_open(read_data="")()

    with patch("os.path.exists", side_effect=fake_exists), patch("builtins.open", side_effect=fake_open):
        topo = detect_linux_topology()
        assert topo is not None
        assert topo.is_heterogeneous is True
        assert topo.detection_method == "linux_sysfs_cpu_core_atom"
        assert topo.p_cores == list(range(16))
        assert topo.e_cores == list(range(16, 24))


def test_simulated_partition_labeling() -> None:
    """Verify that when hardware is non-hybrid, topology is flagged as simulated."""
    with patch("sys.platform", "linux"), patch("os.path.exists", return_value=False):
        topo = detect_cpu_topology()
        assert topo.is_heterogeneous is False
        assert "simulated" in topo.detection_method.lower()


def test_process_affinity_platform_guard() -> None:
    """Verify that platforms without cpu_affinity (e.g. macOS) degrade gracefully."""
    mock_proc = MagicMock()
    # Simulate platform without cpu_affinity attribute
    del mock_proc.cpu_affinity

    with patch("psutil.Process", return_value=mock_proc):
        # Should not raise AttributeError; should return False gracefully
        success = set_process_affinity(pid=9999, cpus=[0, 1])
        assert success is False
