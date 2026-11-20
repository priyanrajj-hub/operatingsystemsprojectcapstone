"""
Security input validation, process identity checking, and constant-time token comparison.
"""

from __future__ import annotations

import hmac
import math

import psutil

from core.exceptions import PIDReuseError, ProcessAuthorizationError


def verify_api_token(provided_token: str | None, expected_token: str) -> bool:
    """Perform constant-time token comparison to prevent timing attacks."""
    if not provided_token or not expected_token:
        return False
    return hmac.compare_digest(provided_token.encode("utf-8"), expected_token.encode("utf-8"))


def validate_hyperparameters(
    alpha: float,
    beta: float,
    exploration: float,
    cold_start: int,
) -> None:
    """Validate numerical stability and sanity bounds for LinUCB hyperparameters."""
    for val, name in [(alpha, "alpha"), (beta, "beta"), (exploration, "exploration")]:
        if not math.isfinite(val):
            raise ValueError(f"Hyperparameter '{name}' must be a finite real number.")
        if val < 0.0:
            raise ValueError(f"Hyperparameter '{name}' cannot be negative.")

    if cold_start < 0 or cold_start > 100000:
        raise ValueError("cold_start must be between 0 and 100,000.")


def validate_process_ownership(
    pid: int,
    expected_start_time: float,
    current_user_only: bool = True,
) -> psutil.Process:
    """
    Verify process identity against PID reuse and foreign user ownership.

    Raises:
        ProcessAuthorizationError: If process is missing or owned by another user.
        PIDReuseError: If process creation time does not match registered timestamp.
    """
    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        raise ProcessAuthorizationError(f"Process {pid} is not accessible: {e}") from e

    try:
        actual_create_time = proc.create_time()
    except Exception as e:
        raise ProcessAuthorizationError(f"Cannot inspect create_time for PID {pid}: {e}") from e

    # Check for recycled PID: creation time must match within 0.1s tolerance
    if abs(actual_create_time - expected_start_time) > 0.1:
        raise PIDReuseError(
            f"PID {pid} reuse detected! Registered at {expected_start_time}, "
            f"actual process created at {actual_create_time}."
        )

    if current_user_only:
        try:
            my_user = psutil.Process().username()
            proc_user = proc.username()
            if my_user != proc_user:
                raise ProcessAuthorizationError(
                    f"Process {pid} is owned by '{proc_user}', not current user '{my_user}'."
                )
        except (psutil.AccessDenied, AttributeError):
            pass

    return proc
