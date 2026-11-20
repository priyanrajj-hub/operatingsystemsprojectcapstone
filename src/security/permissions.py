"""
Role-based access permissions and authorization scopes.
"""

from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    """Granular permissions for API and system actions."""

    READ_TELEMETRY = "telemetry:read"
    RUN_EXPERIMENT = "experiment:run"
    STOP_EXPERIMENT = "experiment:stop"
    RESET_AFFINITY = "affinity:reset"
    ADMIN = "admin"
