"""
Unified hardware topology detector with platform dispatch and fallback mechanisms.
"""

from __future__ import annotations

import logging
import os
import sys

from hardware.linux import detect_linux_topology
from hardware.topology import CoreType, CPUTopology, ProcessorCore
from hardware.windows import detect_windows_topology

logger = logging.getLogger("aidax.hardware.detection")

_CACHED_TOPOLOGY: CPUTopology | None = None


def get_cpu_topology(force_refresh: bool = False) -> CPUTopology:
    """
    Detect system CPU topology across Linux, Windows, and fallback environments.
    Caches result unless force_refresh is True.
    """
    global _CACHED_TOPOLOGY
    if _CACHED_TOPOLOGY is not None and not force_refresh:
        return _CACHED_TOPOLOGY

    topology: CPUTopology | None = None

    if sys.platform.startswith("linux"):
        topology = detect_linux_topology()
    elif sys.platform == "win32":
        topology = detect_windows_topology()

    if topology is None:
        total = os.cpu_count() or 4
        half = max(1, total // 2)
        cores = [
            ProcessorCore(
                core_id=i,
                physical_core_id=i,
                core_type=CoreType.HOMOGENEOUS,
            )
            for i in range(total)
        ]
        topology = CPUTopology(
            total_logical_cores=total,
            total_physical_cores=total,
            is_heterogeneous=False,
            detection_method="simulated_partition_fallback",
            confidence=0.3,
            p_cores=list(range(half)),
            e_cores=list(range(half, total)),
            cores=cores,
        )

    _CACHED_TOPOLOGY = topology
    if not topology.is_heterogeneous:
        logger.warning(
            "SIMULATED PARTITION: Hardware topology does not verify native hybrid cores. "
            "Partitioning %d logical cores [%s] vs [%s] in simulated benchmark mode.",
            topology.total_logical_cores,
            topology.p_cores,
            topology.e_cores,
        )
    logger.info(
        "Detected CPU topology: %d cores, method=%s, heterogeneous=%s, confidence=%.2f",
        topology.total_logical_cores,
        topology.detection_method,
        topology.is_heterogeneous,
        topology.confidence,
    )
    return topology


detect_cpu_topology = get_cpu_topology
