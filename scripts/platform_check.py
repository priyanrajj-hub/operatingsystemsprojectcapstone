#!/usr/bin/env python3
"""
Platform Truth and Hardware Environment Verification Script.

Inspects hardware topology, virtualization, kernel, governor, power state,
thermal conditions, dependencies, and Intel RAPL interface.

Enforces the non-negotiable integrity rule:
Refuses to run real hardware experiments unless executed on native Linux
with hardware-verified hybrid cores, or explicitly granted '--allow-simulated'.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import scipy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.platform_check")


def get_git_commit_hash() -> str:
    """Retrieve current HEAD commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def detect_virtualization() -> str:
    """Detect whether host is native or virtualized (VM, WSL, Docker)."""
    if sys.platform == "win32":
        # Windows host
        return "native_windows"
    try:
        res = subprocess.run(
            ["systemd-detect-virt"],
            capture_output=True,
            text=True,
        )
        virt = res.stdout.strip()
        if virt and res.returncode == 0 and virt != "none":
            return virt
    except Exception:
        pass

    # Check for WSL
    try:
        with open("/proc/version", encoding="utf-8") as f:
            v = f.read().lower()
            if "microsoft" in v or "wsl" in v:
                return "wsl"
    except Exception:
        pass

    # Check for container environment
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return "container"

    return "none"


def inspect_linux_hybrid_sysfs() -> dict[str, Any]:
    """Inspect Linux sysfs for genuine Intel Hybrid architecture counters."""
    core_cpus_path = Path("/sys/devices/cpu_core/cpus")
    atom_cpus_path = Path("/sys/devices/cpu_atom/cpus")

    p_cores: list[int] = []
    e_cores: list[int] = []
    is_genuine_hybrid = False

    def parse_cpulist(text: str) -> list[int]:
        cpus: list[int] = []
        for part in text.strip().split(","):
            if not part:
                continue
            if "-" in part:
                s, e = part.split("-")
                cpus.extend(range(int(s), int(e) + 1))
            else:
                cpus.append(int(part))
        return cpus

    if core_cpus_path.exists() and atom_cpus_path.exists():
        try:
            p_cores = parse_cpulist(core_cpus_path.read_text(encoding="utf-8"))
            e_cores = parse_cpulist(atom_cpus_path.read_text(encoding="utf-8"))
            is_genuine_hybrid = len(p_cores) > 0 and len(e_cores) > 0
        except Exception as e:
            logger.warning("Error reading cpu_core/cpu_atom sysfs: %s", e)

    # Check per-CPU topology core_type (Intel Hybrid sysfs)
    if not is_genuine_hybrid:
        core_type_paths = list(
            Path("/sys/devices/system/cpu/").glob("cpu[0-9]*/topology/core_type")
        )
        if core_type_paths:
            for p in core_type_paths:
                try:
                    cpu_idx = int(p.parent.parent.name.replace("cpu", ""))
                    val = p.read_text(encoding="utf-8").strip()
                    # Intel defines core_type 1 (Core) and 0 (Atom)
                    if val in ("1", "Core"):
                        p_cores.append(cpu_idx)
                    else:
                        e_cores.append(cpu_idx)
                except Exception:
                    pass
            if p_cores and e_cores:
                is_genuine_hybrid = True

    return {
        "is_genuine_hybrid": is_genuine_hybrid,
        "p_cores": sorted(p_cores),
        "e_cores": sorted(e_cores),
    }


def inspect_rapl_availability() -> dict[str, Any]:
    """Check Intel RAPL powercap interface accessibility."""
    rapl_base = Path("/sys/class/powercap/intel-rapl")
    available = rapl_base.exists()
    readable = False
    pkg_energy_path = None
    max_energy_range = None

    if available:
        pkg_path = rapl_base / "intel-rapl:0" / "energy_uj"
        if pkg_path.exists():
            pkg_energy_path = str(pkg_path)
            try:
                val = pkg_path.read_text(encoding="utf-8").strip()
                _ = int(val)
                readable = True
            except (PermissionError, OSError):
                readable = False

        range_path = rapl_base / "intel-rapl:0" / "max_energy_range_uj"
        if range_path.exists():
            try:
                max_energy_range = int(range_path.read_text(encoding="utf-8").strip())
            except Exception:
                pass

    return {
        "rapl_supported": available,
        "rapl_readable": readable,
        "package_energy_path": pkg_energy_path,
        "max_energy_range_uj": max_energy_range,
        "permission_note": (
            "RAPL energy_uj access was restricted by Linux security updates following the PLATYPUS attack (CVE-2020-8694). "
            "To grant least-privilege read access without running as root, configure a dedicated group (e.g., 'rapl'): "
            "sudo groupadd -f rapl && sudo usermod -aG rapl $USER && "
            'echo \'SUBSYSTEM=="powercap", ACTION=="add", RUN+="/bin/chmod -R g+r /sys/class/powercap/intel-rapl"\' | sudo tee /etc/udev/rules.d/99-rapl.rules'
        ),
    }


def inspect_power_and_thermals() -> dict[str, Any]:
    """Inspect battery, AC line, and thermal sensors."""
    on_ac = True
    battery_pct = None
    try:
        batt = psutil.sensors_battery()
        if batt:
            on_ac = batt.power_plugged
            battery_pct = batt.percent
    except Exception:
        pass

    thermals: dict[str, list[float]] = {}
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                thermals[name] = [e.current for e in entries if e.current is not None]
    except Exception:
        pass

    return {
        "on_ac_power": on_ac,
        "battery_percent": battery_pct,
        "temperatures": thermals,
    }


def collect_platform_truth(allow_simulated: bool = False) -> dict[str, Any]:
    """Gathers exhaustive system truth and enforces validity requirements."""
    total_cpus = os.cpu_count() or 1
    virt = detect_virtualization()
    is_linux = sys.platform.startswith("linux")

    hybrid_info = (
        inspect_linux_hybrid_sysfs()
        if is_linux
        else {
            "is_genuine_hybrid": False,
            "p_cores": list(range(max(1, total_cpus // 2))),
            "e_cores": list(range(max(1, total_cpus // 2), total_cpus)),
        }
    )

    rapl_info = (
        inspect_rapl_availability()
        if is_linux
        else {
            "rapl_supported": False,
            "rapl_readable": False,
            "package_energy_path": None,
            "max_energy_range_uj": None,
            "permission_note": "RAPL powercap is only supported natively on Linux bare-metal platforms.",
        }
    )

    power_thermals = inspect_power_and_thermals()

    is_native_bare_metal = virt == "none" or virt == "native_windows"
    is_genuine_hybrid = hybrid_info["is_genuine_hybrid"]

    # Enforce non-negotiable integrity check
    experiment_valid = is_linux and is_native_bare_metal and is_genuine_hybrid

    if not experiment_valid and not allow_simulated:
        error_msg = (
            f"PLATFORM INTEGRITY VIOLATION:\n"
            f"  Host OS: {sys.platform}\n"
            f"  Virtualization: {virt}\n"
            f"  Genuine Hybrid Core sysfs: {is_genuine_hybrid}\n"
            f"AI-DAX will refuse to run publication-grade hardware experiments without native Intel Hybrid cores.\n"
            f"To execute in simulated evaluation mode, pass '--allow-simulated'. All outputs will be tagged explicitly: "
            f"'SIMULATED PARTITION, not real heterogeneity'."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    status_tag = (
        "NATIVE_HYBRID_HARDWARE"
        if experiment_valid
        else "SIMULATED PARTITION, not real heterogeneity"
    )

    data = {
        "status": status_tag,
        "is_simulated": not experiment_valid,
        "timestamp_iso": psutil.boot_time(),
        "git_commit": get_git_commit_hash(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
            "virtualization": virt,
        },
        "cpu": {
            "model": platform.processor(),
            "total_logical_cores": total_cpus,
            "is_genuine_hybrid": is_genuine_hybrid,
            "performance_cores": hybrid_info["p_cores"],
            "efficiency_cores": hybrid_info["e_cores"],
        },
        "power_and_thermals": power_thermals,
        "rapl": rapl_info,
        "software_versions": {
            "python": platform.python_version(),
            "psutil": psutil.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-DAX Platform Truth Verification")
    parser.add_argument(
        "--allow-simulated",
        action="store_true",
        help="Allow running on non-hybrid or non-Linux systems with explicit simulation tagging.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="env.json",
        help="Target JSON file path for recording environment metadata.",
    )
    args = parser.parse_args()

    try:
        env_data = collect_platform_truth(allow_simulated=args.allow_simulated)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(env_data, f, indent=2)
        logger.info(
            "Platform truth verified. Status: %s. Saved to %s", env_data["status"], out_path
        )
    except RuntimeError as e:
        logger.error("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
