"""
Linux CPU Topology Detection via sysfs and cpufreq.
"""

from __future__ import annotations

import glob
import logging
import os

from hardware.topology import CoreType, CPUTopology, ProcessorCore

logger = logging.getLogger("aidax.hardware.linux")


def detect_linux_topology() -> CPUTopology | None:
    """Attempt hardware detection using Linux kernel sysfs core_type files."""
    if not os.path.exists("/sys/devices/system/cpu"):
        return None

    p_cores: list[int] = []
    e_cores: list[int] = []
    cores: list[ProcessorCore] = []

    # 1. Check Intel/Linux core_type (0 = P-core, 1 = E-core)
    core_type_files = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/topology/core_type"))
    if core_type_files:
        for fpath in core_type_files:
            try:
                cpu_id = int(fpath.split("cpu")[1].split("/")[0])
                with open(fpath, encoding="utf-8") as f:
                    c_type_val = int(f.read().strip())
                if c_type_val == 0:
                    c_type = CoreType.PERFORMANCE
                    p_cores.append(cpu_id)
                elif c_type_val == 1:
                    c_type = CoreType.EFFICIENCY
                    e_cores.append(cpu_id)
                else:
                    c_type = CoreType.HOMOGENEOUS

                cores.append(ProcessorCore(core_id=cpu_id, physical_core_id=cpu_id, core_type=c_type))
            except Exception as e:
                logger.debug("Error reading sysfs file %s: %s", fpath, e)

        if p_cores and e_cores:
            total = len(p_cores) + len(e_cores)
            return CPUTopology(
                total_logical_cores=total,
                total_physical_cores=total,
                is_heterogeneous=True,
                detection_method="linux_sysfs_core_type",
                confidence=1.0,
                p_cores=sorted(p_cores),
                e_cores=sorted(e_cores),
                cores=cores,
            )

    # 2. Fallback: Frequency heuristics
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
                p_cores = [c for c, f in freqs.items() if f > threshold]
                e_cores = [c for c, f in freqs.items() if f <= threshold]
                for c, freq_khz in freqs.items():
                    c_type = CoreType.PERFORMANCE if c in p_cores else CoreType.EFFICIENCY
                    cores.append(ProcessorCore(core_id=c, physical_core_id=c, core_type=c_type, max_frequency_mhz=freq_khz / 1000.0))

                return CPUTopology(
                    total_logical_cores=len(freqs),
                    total_physical_cores=len(freqs),
                    is_heterogeneous=True,
                    detection_method="linux_cpufreq_approximation",
                    confidence=0.7,
                    p_cores=sorted(p_cores),
                    e_cores=sorted(e_cores),
                    cores=cores,
                )

    return None
