"""
Security module for AI-DAX authentication, audit logging, and adversarial defenses.
"""

from security.adversarial import (
    context_switch_inflator_kernel,
    cpu_spoofer_kernel,
    feature_mimicry_kernel,
)
from security.audit import AuditEvent, AuditLogger
from security.defenses import (
    MahalanobisAnomalyDetector,
    PerPidRateLimiter,
    RewardWinsorizer,
    RobustScaler,
)
from security.permissions import Permission
from security.validation import (
    validate_hyperparameters,
    validate_process_ownership,
    verify_api_token,
)

__all__ = [
    "AuditEvent",
    "AuditLogger",
    "MahalanobisAnomalyDetector",
    "PerPidRateLimiter",
    "Permission",
    "RewardWinsorizer",
    "RobustScaler",
    "context_switch_inflator_kernel",
    "cpu_spoofer_kernel",
    "feature_mimicry_kernel",
    "validate_hyperparameters",
    "validate_process_ownership",
    "verify_api_token",
]
