"""
Windows CPU Topology Detection via Windows API (GetLogicalProcessorInformationEx) and psutil.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from ctypes import wintypes

import psutil

from hardware.topology import CoreType, CPUTopology, ProcessorCore

logger = logging.getLogger("aidax.hardware.windows")


class _GROUP_AFFINITY(ctypes.Structure):
    _fields_ = [
        ("Mask", ctypes.c_size_t),
        ("Group", wintypes.WORD),
        ("Reserved", wintypes.WORD * 3),
    ]


class _PROCESSOR_RELATIONSHIP(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.BYTE),
        ("EfficiencyClass", wintypes.BYTE),
        ("Reserved", wintypes.BYTE * 20),
        ("GroupCount", wintypes.WORD),
        ("GroupMask", _GROUP_AFFINITY * 1),
    ]


class _SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX(ctypes.Structure):
    _fields_ = [
        ("Relationship", wintypes.DWORD),
        ("Size", wintypes.DWORD),
        ("Processor", _PROCESSOR_RELATIONSHIP),
    ]


def detect_windows_topology() -> CPUTopology | None:
    """
    Inspect Windows processor topology and EfficiencyClass via Win32 API.
    Detects true Intel Hybrid (Alder/Raptor Lake) P-cores vs E-cores when available.
    """
    if sys.platform != "win32":
        return None

    logical_count = psutil.cpu_count(logical=True) or (os.cpu_count() or 4)
    physical_count = psutil.cpu_count(logical=False) or (logical_count // 2 or 1)

    p_cores: list[int] = []
    e_cores: list[int] = []
    cores: list[ProcessorCore] = []
    efficiency_classes_found: set[int] = set()

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        if hasattr(kernel32, "GetLogicalProcessorInformationEx"):
            relation_core = 0  # RelationProcessorCore = 0
            buf_len = wintypes.DWORD(0)
            kernel32.GetLogicalProcessorInformationEx(relation_core, None, ctypes.byref(buf_len))

            if buf_len.value > 0:
                buf = ctypes.create_string_buffer(buf_len.value)
                if kernel32.GetLogicalProcessorInformationEx(
                    relation_core, buf, ctypes.byref(buf_len)
                ):
                    offset = 0
                    phys_id = 0
                    while offset < buf_len.value:
                        item = _SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX.from_buffer_copy(
                            buf, offset
                        )
                        if item.Relationship == relation_core:
                            eff = item.Processor.EfficiencyClass
                            efficiency_classes_found.add(eff)
                            mask = item.Processor.GroupMask[0].Mask
                            flags = item.Processor.Flags
                            is_smt = (flags & 1) != 0

                            for bit in range(64):
                                if (mask >> bit) & 1:
                                    c_type = (
                                        CoreType.PERFORMANCE if eff > 0 else CoreType.EFFICIENCY
                                    )
                                    if eff > 0:
                                        p_cores.append(bit)
                                    else:
                                        e_cores.append(bit)
                                    cores.append(
                                        ProcessorCore(
                                            core_id=bit,
                                            physical_core_id=phys_id,
                                            core_type=c_type,
                                            is_smt=is_smt,
                                        )
                                    )
                            phys_id += 1
                        offset += item.Size
    except Exception as e:
        logger.debug("Windows API processor query error: %s", e)

    p_cores.sort()
    e_cores.sort()

    # If distinct efficiency classes (e.g. 0 and 1) were discovered, we have verified hybrid hardware
    if len(efficiency_classes_found) >= 2 and p_cores and e_cores:
        return CPUTopology(
            total_logical_cores=logical_count,
            total_physical_cores=physical_count,
            is_heterogeneous=True,
            detection_method="windows_kernel32_efficiency_class",
            confidence=1.0,
            p_cores=p_cores,
            e_cores=e_cores,
            cores=cores,
        )

    # Otherwise, fallback to homogeneous or simulated core partitioning
    half = max(1, logical_count // 2)
    p_cores = list(range(half))
    e_cores = list(range(half, logical_count))
    fallback_cores: list[ProcessorCore] = []

    for i in range(logical_count):
        fallback_cores.append(
            ProcessorCore(
                core_id=i,
                physical_core_id=i // 2 if logical_count > physical_count else i,
                core_type=CoreType.HOMOGENEOUS,
            )
        )

    return CPUTopology(
        total_logical_cores=logical_count,
        total_physical_cores=physical_count,
        is_heterogeneous=False,
        detection_method="windows_homogeneous_simulated",
        confidence=0.5,
        p_cores=p_cores,
        e_cores=e_cores,
        cores=fallback_cores,
    )
