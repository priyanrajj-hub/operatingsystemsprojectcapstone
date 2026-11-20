"""
CPU Topology and Processor Architecture models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CoreType(str, Enum):
    """Core efficiency and performance classification."""

    PERFORMANCE = "P-core"
    EFFICIENCY = "E-core"
    HOMOGENEOUS = "Standard"
    UNKNOWN = "Unknown"


@dataclass
class ProcessorCore:
    """Information regarding a single logical/physical processor core."""

    core_id: int
    physical_core_id: int
    core_type: CoreType = CoreType.UNKNOWN
    max_frequency_mhz: float = 0.0
    numa_node: int = 0
    is_smt: bool = False


@dataclass
class CPUTopology:
    """System-wide processor topology summary."""

    total_logical_cores: int
    total_physical_cores: int
    is_heterogeneous: bool
    detection_method: str
    confidence: float  # 0.0 to 1.0
    p_cores: list[int] = field(default_factory=list)
    e_cores: list[int] = field(default_factory=list)
    cores: list[ProcessorCore] = field(default_factory=list)

    @property
    def all_cores(self) -> list[int]:
        """Return all available core indices."""
        return list(range(self.total_logical_cores))

    def to_dict(self) -> dict[str, Any]:
        """Convert topology to serializable dictionary."""
        d = asdict(self)
        d["cores"] = [asdict(c) for c in self.cores]
        return d
