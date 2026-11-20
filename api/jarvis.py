"""
Vercel Serverless Function: Jarvis Assistant Speech Proxy (/api/jarvis)
Provides a secure server-side bridge for voice interaction queries without leaking API keys.
Strictly relies on Python standard library for zero-dependency execution on Vercel.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from http.server import BaseHTTPRequestHandler
from typing import Any

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
                {"response": "Speech assistant rate limit reached. Please wait a moment."},
            )
            return

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or api_key.startswith("your_") or "placeholder" in api_key.lower():
            self._send_json(
                200,
                {
                    "response": "Jarvis Cloud Assistant offline: GEMINI_API_KEY not configured in Vercel environment."
                },
            )
            return

        # Read and validate request body
        try:
            content_length = int(self.headers.get("content-length", 0))
            if content_length > 4096:
                self._send_json(400, {"response": "Query payload exceeds maximum size."})
                return
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8", errors="replace"))
        except Exception:
            self._send_json(400, {"response": "Invalid request formatting."})
            return

        raw_query = str(payload.get("voice_query", ""))
        raw_lang = str(payload.get("language", "English"))
        cpu_overall = float(payload.get("cpu_percent_overall", 0.0))

        # Sanitize query and language inputs
        clean_query = re.sub(r"[\r\n\t]", " ", raw_query).strip()[:200]
        clean_lang = re.sub(r"[^A-Za-z0-9 -]", "", raw_lang).strip()[:30] or "English"

        if not clean_query:
            self._send_json(
                200, {"response": "Jarvis listening. How can I assist you with the CPU governor?"}
            )
            return

        prompt = (
            f"You are Jarvis, an operating system assistant. User says: '{clean_query}'. "
            f"Language: '{clean_lang}'. Current CPU: {cpu_overall:.1f}%. "
            f"Respond concisely in '{clean_lang}' exclusively."
        )

        req_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 200},
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
                    raise ValueError("No candidate parts returned from speech API")
                text = (
                    candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                )
                self._send_json(200, {"response": text[:400]})
                return
        except Exception:
            pass

        self._send_json(
            200,
            {
                "response": "Speech assistant is temporarily unavailable. Core scheduler is operating normally."
            },
        )
