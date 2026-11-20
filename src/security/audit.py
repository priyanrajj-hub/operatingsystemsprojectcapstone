"""
Security audit event recording and memory store.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("aidax.security.audit")


@dataclass
class AuditEvent:
    """Security event record."""

    action: str
    actor: str
    ip_address: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class AuditLogger:
    """In-memory security audit log with capped retention."""

    def __init__(self, max_records: int = 1000) -> None:
        self.max_records = max_records
        self.events: list[AuditEvent] = []

    def record(
        self,
        action: str,
        actor: str,
        ip_address: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a security event."""
        event = AuditEvent(
            action=action,
            actor=actor,
            ip_address=ip_address,
            status=status,
            details=details or {},
        )
        self.events.append(event)
        if len(self.events) > self.max_records:
            self.events = self.events[-self.max_records :]
        logger.info(
            "AUDIT_EVENT: action=%s actor=%s ip=%s status=%s",
            action,
            actor,
            ip_address,
            status,
        )

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit events as dictionaries."""
        return [asdict(e) for e in self.events[-limit:]]


audit_log = AuditLogger()
