"""
Vercel Serverless Function: Aizen AI Insights Proxy (/api/aizen)
Provides a secure server-side bridge to Google Gemini without exposing credentials.
Strictly relies on Python standard library for zero-dependency execution on Vercel.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler
from typing import Any

# In-memory rate limiting across invocations on warm containers
_request_log: dict[str, list[float]] = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 10
RATE_LIMIT_WINDOW = 60.0


def is_rate_limited(client_ip: str) -> bool:
    """Check if the client IP has exceeded the allowed request frequency."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    timestamps = [t for t in _request_log[client_ip] if t > cutoff]
    if len(timestamps) >= MAX_REQUESTS_PER_MINUTE:
        return True
    timestamps.append(now)
    _request_log[client_ip] = timestamps
    return False


class handler(BaseHTTPRequestHandler):
    """Vercel serverless request handler."""

    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def do_POST(self) -> None:
        client_ip = (
            self.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or self.client_address[0]
            or "127.0.0.1"
        )

        if is_rate_limited(client_ip):
            self._send_json(
                429,
                {
                    "health": "Rate Limit Exceeded",
                    "process": f"Max {MAX_REQUESTS_PER_MINUTE} requests/min. Please wait before retrying.",
                    "future": "Local scheduler is unaffected.",
                },
            )
            return

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or api_key.startswith("your_") or "placeholder" in api_key.lower():
            self._send_json(
                200,
                {
                    "health": "Aizen Preview Mode",
                    "process": "GEMINI_API_KEY is not configured in Vercel environment variables.",
                    "future": "Configure GEMINI_API_KEY in Vercel project settings to enable cloud LLM insights.",
                },
            )
            return

        # Read and validate request body
        try:
            content_length = int(self.headers.get("content-length", 0))
            if content_length > 8192:
                self._send_json(400, {"error": "Payload Too Large"})
                return
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8", errors="replace"))
        except Exception:
            self._send_json(400, {"error": "Invalid JSON Payload"})
            return

        cpu_overall = float(payload.get("cpu_percent_overall", 0.0))
        mem_percent = float(payload.get("memory_percent", 0.0))
        decisions = int(payload.get("total_decisions", 0))
        regret = float(payload.get("regret", 0.0))

        prompt = (
            f"You are 'Aizen', an OS kernel AI governor. CPU: {cpu_overall:.1f}% "
            f"Memory: {mem_percent:.1f}%. LinUCB decisions: {decisions} "
            f"Regret: {regret:.2f}\nProvide 3 concise insights: 1. Computer Health "
            f"2. Process Management Insights 3. Future Use & What can be done.\n"
            "Return EXACTLY a JSON array with 3 string elements: "
            '["health", "process", "future"]. Respond in English.'
        )

        req_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
        }

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        req = urllib.request.Request(
            url,
            data=json.dumps(req_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if not candidates:
                    raise ValueError("No candidates returned from API")
                text = (
                    candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                )

                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                clean = text.strip()

                parsed = json.loads(clean)
                if isinstance(parsed, list) and len(parsed) >= 3:
                    self._send_json(
                        200,
                        {
                            "health": str(parsed[0])[:200],
                            "process": str(parsed[1])[:200],
                            "future": str(parsed[2])[:200],
                        },
                    )
                    return
        except Exception:
            pass

        # Safe fallback response if inference fails or parses unexpectedly
        self._send_json(
            200,
            {
                "health": "System Operational (Deterministic Mode)",
                "process": "Autonomous LinUCB contextual core is scheduling active tasks.",
                "future": "Telemetry streaming is nominal.",
            },
        )
