"""
AI-DAX: Adaptive Intelligence for Dynamic Allocation & eXecution.

An adaptive contextual bandit CPU scheduling simulator using LinUCB,
a FastAPI telemetry backend, and reproducible evaluation harnesses.
"""

__version__ = "1.0.0"

from aidax.scheduler import AIScheduler, LinUCBArm, LinUCBBandit, OnlineScaler, SchedulerConfig
from aidax.workload import spawn_workload

__all__ = [
    "__version__",
    "AIScheduler",
    "LinUCBArm",
    "LinUCBBandit",
    "OnlineScaler",
    "SchedulerConfig",
    "spawn_workload",
]
