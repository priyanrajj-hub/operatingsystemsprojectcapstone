"""
AI-DAX Lite: FastAPI Dashboard Backend
======================================
Serves the HTML/JS frontend and provides REST + WebSocket endpoints
for live CPU health monitoring, bandit telemetry, and emergency reset.

Endpoints:
  GET  /                  — Redirect to the static frontend
  GET  /api/live          — Latest scheduler state from CSV
  GET  /api/history       — Last N rows for time-series charting
  POST /api/reset         — Emergency CPU affinity reset across all tracked tasks
  GET  /api/bandit-stats  — Bandit parameters, regret, and decision ratios
  POST /api/aizen         — Telemetry analysis panel
  POST /api/jarvis        — Assistant interaction endpoint
  WS   /ws/live           — WebSocket streaming metrics every 1s
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
from io import StringIO
from pathlib import Path
from typing import Any

import psutil
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("aidax.api")

app = FastAPI(title="AI-DAX Lite Dashboard", version="1.0.0")

# Optional Gemini Integration
API_KEY = os.environ.get("GEMINI_API_KEY", "")
_genai_available = False
if API_KEY:
    try:
        import google.generativeai as genai

        genai.configure(api_key=API_KEY)
        _genai_available = True
    except Exception as e:
        logger.warning("Could not initialize google.generativeai: %s", e)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE = os.environ.get("AIDAX_LOG_FILE", "scheduler_log.csv")
PID_FILE = os.environ.get("AIDAX_PID_FILE", "pids.txt")
BANDIT_STATS_FILE = os.environ.get("AIDAX_STATS_FILE", "bandit_stats.json")


def read_csv_safe(max_rows: int = 300) -> list[dict[str, str]]:
    """Read scheduler log CSV defensively, returning the most recent rows."""
    rows: list[dict[str, str]] = []
    try:
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            return rows
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            content = f.read()
        reader = csv.DictReader(StringIO(content))
        all_rows = list(reader)
        rows = all_rows[-max_rows:]
    except Exception as e:
        logger.debug("Error reading CSV safe: %s", e)
    return rows


def reset_all_affinities() -> int:
    """Emergency reset: release all tracked processes from specific core affinities."""
    total_cores = os.cpu_count() or 4
    all_cores = list(range(total_cores))
    count = 0

    if not os.path.exists(PID_FILE):
        return count

    current_username: str | None = None
    try:
        current_username = psutil.Process().username()
    except Exception:
        pass

    try:
        with open(PID_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    pid = data["pid"]
                    start_time = data["start_time"]
                    p = psutil.Process(pid)
                    if p.create_time() == start_time:
                        if current_username is None or p.username() == current_username:
                            p.cpu_affinity(all_cores)
                            count += 1
                except Exception:
                    continue
    except FileNotFoundError:
        pass

    return count


def get_system_health() -> dict[str, Any]:
    """Gather host CPU and memory health metrics."""
    cpu_percent_per_core = psutil.cpu_percent(percpu=True)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()

    return {
        "cpu_percent_overall": psutil.cpu_percent(),
        "cpu_percent_per_core": cpu_percent_per_core,
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_freq_current": cpu_freq.current if cpu_freq else 0,
        "cpu_freq_max": cpu_freq.max if cpu_freq else 0,
        "cpu_freq_min": cpu_freq.min if cpu_freq else 0,
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_percent": mem.percent,
    }


def read_bandit_stats() -> dict[str, Any]:
    """Read bandit parameter state written atomically by the scheduler."""
    try:
        if os.path.exists(BANDIT_STATS_FILE):
            with open(BANDIT_STATS_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug("Error reading bandit stats: %s", e)

    return {
        "total_decisions": 0,
        "heuristic_count": 0,
        "bandit_count": 0,
        "cumulative_regret": 0.0,
    }


# ─────────────────────────────────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────────────────────────────────


@app.get("/api/live")
def api_live() -> JSONResponse:
    """Return latest decision cycle state for monitored processes."""
    rows = read_csv_safe(max_rows=50)
    if not rows:
        return JSONResponse({"processes": [], "timestamp": None, "count": 0})

    latest_ts = rows[-1].get("timestamp", "")
    recent = [r for r in rows if r.get("timestamp") == latest_ts]
    return JSONResponse(
        {
            "processes": recent,
            "timestamp": latest_ts,
            "count": len(recent),
        }
    )


@app.get("/api/history")
def api_history(limit: int = 100) -> JSONResponse:
    """Return historical time series data for telemetry charting."""
    rows = read_csv_safe(max_rows=limit)
    return JSONResponse({"history": rows, "count": len(rows)})


@app.post("/api/reset")
def api_reset() -> JSONResponse:
    """Emergency endpoint: releases affinities across all tracked processes."""
    released = reset_all_affinities()
    return JSONResponse(
        {
            "status": "success",
            "released_processes": released,
            "message": f"Successfully cleared affinities on {released} process(es).",
        }
    )


@app.get("/api/bandit-stats")
def api_bandit_stats() -> JSONResponse:
    """Return LinUCB decision distribution and cumulative regret metrics."""
    stats = read_bandit_stats()
    total = stats.get("heuristic_count", 0) + stats.get("bandit_count", 0)
    if total > 0:
        stats["heuristic_pct"] = round(stats["heuristic_count"] / total * 100, 1)
        stats["bandit_pct"] = round(stats["bandit_count"] / total * 100, 1)
    else:
        stats["heuristic_pct"] = 0.0
        stats["bandit_pct"] = 0.0
    return JSONResponse(stats)


class TelemetryPayload(BaseModel):
    cpu_percent_overall: float
    memory_percent: float
    total_decisions: int
    regret: float
    voice_query: str = ""
    language: str = "English"


@app.post("/api/aizen")
async def api_aizen(payload: TelemetryPayload) -> JSONResponse:
    """Aizen AI telemetry insights panel endpoint."""
    if not API_KEY or not _genai_available:
        return JSONResponse(
            {
                "health": "Aizen Offline: No API Key",
                "process": "Please configure GEMINI_API_KEY in your .env file",
                "future": "Restart the Python backend after setting the key.",
            }
        )

    prompt = (
        f"You are 'Aizen', a deep-system OS kernel AI. CPU: {payload.cpu_percent_overall}% "
        f"Memory: {payload.memory_percent}%. LinUCB acts: {payload.total_decisions} "
        f"Regret: {payload.regret}\nProvide 3 concise insights: 1. Computer Health "
        f"2. Process Management Insights 3. Future Use & What can be done.\n"
        "Return EXACTLY a JSON array with 3 string elements: "
        '["health", "process", "future"]. Respond in English.'
    )
    try:
        import ast

        import google.generativeai as genai

        model = genai.GenerativeModel("gemini-flash-lite-latest")
        resp = await asyncio.to_thread(model.generate_content, prompt)
        raw_text = resp.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        clean_text = raw_text.strip()
        val = ast.literal_eval(clean_text)
        return JSONResponse({"health": val[0], "process": val[1], "future": val[2]})
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            return JSONResponse(
                {
                    "health": "System nominal (AI Cooldown Active)",
                    "process": "Quota limit reached; analytics will resume automatically.",
                    "future": "Core LinUCB scheduling operates independently of cloud LLMs.",
                }
            )
        return JSONResponse(
            {
                "health": "Error running Aizen AI",
                "process": err_str[:120],
                "future": "",
            }
        )


@app.post("/api/jarvis")
async def api_jarvis(payload: TelemetryPayload) -> JSONResponse:
    """Multilingual assistant endpoint."""
    if not API_KEY or not _genai_available:
        return JSONResponse({"response": "Speech assistant offline: missing GEMINI_API_KEY."})

    prompt = (
        f"You are Jarvis, an operating system assistant. User says: '{payload.voice_query}'. "
        f"Language: '{payload.language}'. Current CPU: {payload.cpu_percent_overall}%. "
        f"Respond concisely in '{payload.language}' exclusively."
    )
    try:
        import google.generativeai as genai

        model = genai.GenerativeModel("gemini-flash-lite-latest")
        resp = await asyncio.to_thread(model.generate_content, prompt)
        return JSONResponse({"response": resp.text.strip()})
    except Exception:
        return JSONResponse({"response": "Error reaching language model server."})


# ─────────────────────────────────────────────────────────────────────
# WebSocket Endpoint
# ─────────────────────────────────────────────────────────────────────


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    """Stream live process and telemetry updates every 1 second."""
    await websocket.accept()
    try:
        while True:
            rows = read_csv_safe(max_rows=50)
            if rows:
                latest_ts = rows[-1].get("timestamp", "")
                recent = [r for r in rows if r.get("timestamp") == latest_ts]
            else:
                recent = []

            payload = {
                "processes": recent,
                "system": get_system_health(),
                "bandit": read_bandit_stats(),
                "history_tail": read_csv_safe(max_rows=100),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# Static Files & Dashboard Entry
# ─────────────────────────────────────────────────────────────────────


def _find_static_dir() -> Path:
    """Locate the static files directory across local runs and installations."""
    candidates = [
        Path.cwd() / "static",
        Path(__file__).resolve().parent.parent.parent / "static",
        Path(__file__).resolve().parent / "static",
    ]
    for c in candidates:
        if c.is_dir() and (c / "index.html").exists():
            return c
    # Fallback default
    fallback = Path.cwd() / "static"
    fallback.mkdir(exist_ok=True)
    return fallback


STATIC_DIR = _find_static_dir()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_root() -> RedirectResponse:
    """Redirect root access to static index.html dashboard."""
    return RedirectResponse(url="/static/index.html")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch uvicorn server running the dashboard app."""
    import uvicorn

    uvicorn.run("aidax.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_server()
