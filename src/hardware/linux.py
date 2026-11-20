"""
Linux CPU Topology Detection via sysfs, cpu_core/cpu_atom, and cpufreq.
"""

from __future__ import annotations

import glob
import logging
import os
import re

from hardware.topology import CoreType, CPUTopology, ProcessorCore

logger = logging.getLogger("aidax.hardware.linux")


def parse_cpulist(cpulist_str: str) -> list[int]:
    """
    Parse a Linux sysfs CPU range list string (e.g. '0-3,8,10-12') into a list of CPU IDs.
    """
    cpus: set[int] = set()
    cleaned = cpulist_str.strip()
    if not cleaned:
        return []

    for part in cleaned.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            match = re.match(r"^(\d+)-(\d+)$", part)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                cpus.update(range(start, end + 1))
        else:
            try:
                cpus.add(int(part))
            except ValueError:
                pass
    return sorted(cpus)


def detect_linux_topology() -> CPUTopology | None:
    """Attempt hardware detection using Linux kernel sysfs nodes."""
    if not os.path.exists("/sys/devices/system/cpu"):
        return None

    # 1. Primary Gold Standard: /sys/devices/cpu_core/cpus and /sys/devices/cpu_atom/cpus (Intel Hybrid on Linux 5.18+)
    core_path = "/sys/devices/cpu_core/cpus"
    atom_path = "/sys/devices/cpu_atom/cpus"
    if os.path.exists(core_path) and os.path.exists(atom_path):
        try:
            with open(core_path, encoding="utf-8") as f:
                p_cores = parse_cpulist(f.read())
            with open(atom_path, encoding="utf-8") as f:
                e_cores = parse_cpulist(f.read())

            if p_cores and e_cores:
                total = len(p_cores) + len(e_cores)
                cores = [
                    ProcessorCore(
                        core_id=c,
                        physical_core_id=c,
                        core_type=CoreType.PERFORMANCE if c in p_cores else CoreType.EFFICIENCY,
                    )
                    for c in sorted(p_cores + e_cores)
                ]
                logger.info(
                    "Detected Intel Hybrid architecture via cpu_core/cpu_atom sysfs: P=%s, E=%s",
                    p_cores,
                    e_cores,
                )
                return CPUTopology(
                    total_logical_cores=total,
                    total_physical_cores=total,
                    is_heterogeneous=True,
                    detection_method="linux_sysfs_cpu_core_atom",
                    confidence=1.0,
                    p_cores=p_cores,
                    e_cores=e_cores,
                    cores=cores,
                )
        except Exception as e:
            logger.debug("Failed reading cpu_core/cpu_atom sysfs: %s", e)

    p_cores_list: list[int] = []
    e_cores_list: list[int] = []
    cores_list: list[ProcessorCore] = []

    # 2. Check individual core_type (0 = P-core, 1 = E-core)
    core_type_files = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/topology/core_type"))
    if core_type_files:
        for fpath in core_type_files:
            try:
                cpu_id = int(fpath.split("cpu")[1].split("/")[0])
                with open(fpath, encoding="utf-8") as f:
                    c_type_val = int(f.read().strip())
                if c_type_val == 0:
                    c_type = CoreType.PERFORMANCE
                    p_cores_list.append(cpu_id)
                elif c_type_val == 1:
                    c_type = CoreType.EFFICIENCY
                    e_cores_list.append(cpu_id)
                else:
                    c_type = CoreType.HOMOGENEOUS

                cores_list.append(
                    ProcessorCore(core_id=cpu_id, physical_core_id=cpu_id, core_type=c_type)
                )
            except Exception as e:
                logger.debug("Error reading sysfs file %s: %s", fpath, e)

        if p_cores_list and e_cores_list:
            total = len(p_cores_list) + len(e_cores_list)
            return CPUTopology(
                total_logical_cores=total,
                total_physical_cores=total,
                is_heterogeneous=True,
                detection_method="linux_sysfs_core_type",
                confidence=1.0,
                p_cores=sorted(p_cores_list),
                e_cores=sorted(e_cores_list),
                cores=cores_list,
            )

    # 3. Fallback: Frequency heuristics
    freq_files = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/cpuinfo_max_freq"))
    if freq_files:
        freqs: dict[int, int] = {}
        for fpath in freq_files:
            try:
                cpu_id = int(fpath.split("cpu")[1].split("/")[0])
                with open(fpath, encoding="utf-8") as f:
                    freqs[cpu_id] = int(f.read().strip())
            except Exception:
                pass

        if freqs:
            unique_freqs = sorted(set(freqs.values()), reverse=True)
            if len(unique_freqs) > 1:
                threshold = (unique_freqs[0] + unique_freqs[-1]) / 2.0
                p_cores_freq = [c for c, f in freqs.items() if f > threshold]
                e_cores_freq = [c for c, f in freqs.items() if f <= threshold]
                for c, freq_khz in freqs.items():
                    c_type = CoreType.PERFORMANCE if c in p_cores_freq else CoreType.EFFICIENCY
                    cores_list.append(
                        ProcessorCore(
                            core_id=c,
                            physical_core_id=c,
                            core_type=c_type,
                            max_frequency_mhz=freq_khz / 1000.0,
                        )
                    )

                return CPUTopology(
                    total_logical_cores=len(freqs),
                    total_physical_cores=len(freqs),
                    is_heterogeneous=True,
                    detection_method="linux_cpufreq_approximation",
                    confidence=0.7,
                    p_cores=sorted(p_cores_freq),
                    e_cores=sorted(e_cores_freq),
                    cores=cores_list,
                )

    return None
