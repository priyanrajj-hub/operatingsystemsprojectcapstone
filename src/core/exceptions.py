"""
Domain-specific exceptions for AI-DAX.
"""

from __future__ import annotations


class AIDAXError(Exception):
    """Base exception for all AI-DAX errors."""


class SecurityError(AIDAXError):
    """Raised when an operation violates security policy or authentication boundaries."""


class ProcessAuthorizationError(SecurityError):
    """Raised when an operation attempts to manipulate an unauthorized or unmanaged PID."""


class PIDReuseError(SecurityError):
    """Raised when a PID recycle or creation-timestamp mismatch is detected."""


class TopologyError(AIDAXError):
    """Raised when hardware topology cannot be inspected or resolved safely."""


class CheckpointError(AIDAXError):
    """Raised when model checkpoint state is corrupted, incompatible, or invalid."""


class ProcessControlError(AIDAXError):
    """Raised when process spawning, affinity manipulation, or termination fails."""


class WorkloadError(AIDAXError):
    """Raised when workload lifecycle management encounters a fault."""


class ExperimentError(AIDAXError):
    """Raised during experiment configuration or execution failures."""
