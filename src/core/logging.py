"""
Structured logging module for AI-DAX with CWE-117 log injection sanitization.
"""

from __future__ import annotations

import logging
import re
import sys


def sanitize_log_message(msg: str) -> str:
    """Sanitize log string against CRLF injection and control character abuse."""
    if not isinstance(msg, str):
        msg = str(msg)
    # Replace newlines and carriage returns with escaped representations
    cleaned = msg.replace("\r", "\\r").replace("\n", "\\n")
    # Redact common token patterns
    cleaned = re.sub(r"(AIza[0-9A-Za-z-_]{35})", "[REDACTED_API_KEY]", cleaned)
    cleaned = re.sub(r"(Bearer\s+[A-Za-z0-9-_.]+)", "Bearer [REDACTED_TOKEN]", cleaned)
    return cleaned


class SanitizedFormatter(logging.Formatter):
    """Logging formatter that intercepts and sanitizes record messages."""

    def format(self, record: logging.LogRecord) -> str:
        record.msg = sanitize_log_message(str(record.msg))
        return super().format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Initialize structured logging across the application."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = SanitizedFormatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]
