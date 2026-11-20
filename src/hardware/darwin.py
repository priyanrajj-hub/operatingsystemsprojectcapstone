"""
macOS CPU Topology Detection and Platform Disclosure.
"""

from __future__ import annotations

import logging
import os
import sys

import psutil

from hardware.topology import CoreType, CPUTopology, ProcessorCore

logger = logging.getLogger("aidax.hardware.darwin")


def detect_darwin_topology() -> CPUTopology | None:
    """
    Detect macOS processor topology and explicitly report affinity limitations.
    macOS Mach kernel does not support thread or process CPU affinity binding.
    """
    if sys.platform != "darwin":
        return None

    logical_count = psutil.cpu_count(logical=True) or (os.cpu_count() or 4)
    physical_count = psutil.cpu_count(logical=False) or (logical_count // 2 or 1)

    logger.warning(
        "macOS Mach kernel detected: OS-level CPU process affinity is unsupported. "
        "Heterogeneous topology unavailable for direct affinity binding."
    )

    cores = [
        ProcessorCore(
            core_id=i,
            physical_core_id=i // 2 if logical_count > physical_count else i,
            core_type=CoreType.UNKNOWN,
        )
        for i in range(logical_count)
    ]

    return CPUTopology(
        total_logical_cores=logical_count,
        total_physical_cores=physical_count,
        is_heterogeneous=False,
        detection_method="darwin_mach_unsupported",
        confidence=0.0,
        p_cores=[],
        e_cores=[],
        cores=cores,
    )
