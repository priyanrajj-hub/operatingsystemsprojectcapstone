"""
Sliding-window IP-based rate limiting middleware.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Restricts per-IP request frequency to mitigate denial-of-service and brute-force attacks."""

    def __init__(self, app: Any, max_requests: int = 120, window_seconds: float = 60.0) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests_log: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # Exempt static assets and health check endpoints
        path = request.url.path
        if path.startswith("/static") or path in ("/health", "/api/v1/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - self.window_seconds

        # Prune older entries
        timestamps = [t for t in self.requests_log[client_ip] if t > window_start]
        if len(timestamps) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds}s.",
                },
                headers={"Retry-After": str(int(self.window_seconds))},
            )

        timestamps.append(now)
        self.requests_log[client_ip] = timestamps
        return await call_next(request)
