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
import re
import time
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.config import settings

logger = logging.getLogger("aidax.api")

app = FastAPI(title="AI-DAX Lite Dashboard", version="1.0.0")

# Centralized Settings & Optional Gemini Integration
API_KEY = settings.gemini_api_key
_genai_available = False
if API_KEY and not API_KEY.startswith("your_") and "placeholder" not in API_KEY.lower():
    try:
        import google.generativeai as genai

        genai.configure(api_key=API_KEY)
        _genai_available = True
    except Exception as e:
        logger.warning("Could not initialize google.generativeai: %s", type(e).__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

LOG_FILE = settings.log_file
PID_FILE = settings.pid_file
BANDIT_STATS_FILE = settings.stats_file

# Sliding-window IP Rate Limiter for AI Proxy Endpoints (max 10 req/min per IP)
_ai_request_log: dict[str, list[float]] = defaultdict(list)
MAX_AI_REQUESTS_PER_MINUTE = 10
AI_RATE_LIMIT_WINDOW = 60.0


def check_ai_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    cutoff = now - AI_RATE_LIMIT_WINDOW
    timestamps = [t for t in _ai_request_log[client_ip] if t > cutoff]
    if len(timestamps) >= MAX_AI_REQUESTS_PER_MINUTE:
        return False
    timestamps.append(now)
    _ai_request_log[client_ip] = timestamps
    return True


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
    """Gather host CPU, memory, and hardware topology health metrics."""
    cpu_percent_per_core = psutil.cpu_percent(percpu=True)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    uptime_s = time.time() - psutil.boot_time()

    from hardware.detection import get_cpu_topology

    topo = get_cpu_topology()

    return {
        "cpu_percent_overall": psutil.cpu_percent(),
        "cpu_percent_per_core": cpu_percent_per_core,
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_freq_current": round(cpu_freq.current, 1) if cpu_freq else 0,
        "cpu_freq_max": round(cpu_freq.max, 1) if (cpu_freq and cpu_freq.max) else None,
        "cpu_freq_min": round(cpu_freq.min, 1) if (cpu_freq and cpu_freq.min) else None,
        "system_uptime_seconds": round(uptime_s, 1),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_percent": mem.percent,
        "is_heterogeneous": topo.is_heterogeneous,
        "is_simulated": not topo.is_heterogeneous,
        "p_cores": topo.p_cores,
        "e_cores": topo.e_cores,
        "topology_status": (
            "Verified Heterogeneous Hybrid"
            if topo.is_heterogeneous
            else "Heterogeneous topology unavailable"
        ),
        "timestamp": time.time(),
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


@app.get("/api/health")
def api_health() -> JSONResponse:
    """System health check endpoint."""
    return JSONResponse({"status": "ok", "service": "aidax-dashboard", "version": "1.0.0"})


@app.get("/api/system")
def api_system() -> JSONResponse:
    """Return live host system CPU, memory, and topology metrics."""
    return JSONResponse(get_system_health())


@app.get("/api/processes")
def api_processes() -> JSONResponse:
    """Return list of active processes tracked in pids.txt with full metrics."""
    procs: list[dict[str, Any]] = []
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                        pid = item.get("pid")
                        if pid and psutil.pid_exists(pid):
                            p = psutil.Process(pid)
                            item["name"] = p.name()
                            item["cpu_percent"] = p.cpu_percent(interval=0.0)
                            item["memory_percent"] = round(p.memory_percent(), 2)
                            item["status"] = p.status()
                            try:
                                item["current_affinity"] = list(p.cpu_affinity())
                            except (AttributeError, psutil.AccessDenied):
                                item["current_affinity"] = []
                            procs.append(item)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Error reading PID file: %s", e)
    return JSONResponse({"processes": procs, "count": len(procs)})


@app.get("/api/hardware")
def api_hardware() -> JSONResponse:
    """Return verified CPU hardware topology."""
    from hardware.detection import get_cpu_topology

    topo = get_cpu_topology()
    return JSONResponse(topo.to_dict())


@app.get("/api/telemetry")
def api_telemetry() -> JSONResponse:
    """Return consolidated telemetry snapshot (system health + bandit stats)."""
    return JSONResponse(
        {
            "system": get_system_health(),
            "bandit": read_bandit_stats(),
            "timestamp": time.time(),
        }
    )


@app.get("/api/scheduler/status")
def api_scheduler_status() -> JSONResponse:
    """Return scheduler operational state and process counts."""
    pids_count = 0
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                pids_count = sum(1 for line in f if line.strip())
        except Exception:
            pass

    return JSONResponse(
        {
            "status": "running" if pids_count > 0 else "idle",
            "tracked_processes": pids_count,
            "log_file_present": os.path.exists(LOG_FILE),
            "stats_file_present": os.path.exists(BANDIT_STATS_FILE),
        }
    )


@app.post("/api/scheduler/start")
def api_scheduler_start(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> JSONResponse:
    """Signal scheduler startup / active mode."""
    expected_token = os.getenv("AIDAX_API_TOKEN", "")
    if expected_token:
        from security.validation import verify_api_token

        if not verify_api_token(x_api_token, expected_token):
            raise HTTPException(
                status_code=401, detail="Unauthorized: invalid or missing API token"
            )

    return JSONResponse({"status": "running", "message": "Scheduler signal active"})


@app.post("/api/scheduler/stop")
def api_scheduler_stop(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> JSONResponse:
    """Signal scheduler stop."""
    expected_token = os.getenv("AIDAX_API_TOKEN", "")
    if expected_token:
        from security.validation import verify_api_token

        if not verify_api_token(x_api_token, expected_token):
            raise HTTPException(
                status_code=401, detail="Unauthorized: invalid or missing API token"
            )

    return JSONResponse({"status": "idle", "message": "Scheduler signal stopped"})


class AffinityUpdateRequest(BaseModel):
    cores: list[int] = Field(description="Target logical core indices")


@app.post("/api/process/{pid}/affinity")
def api_set_process_affinity(
    pid: int,
    payload: AffinityUpdateRequest,
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> JSONResponse:
    """Safely update affinity of a managed process with PID validation."""
    expected_token = os.getenv("AIDAX_API_TOKEN", "")
    if expected_token:
        from security.validation import verify_api_token

        if not verify_api_token(x_api_token, expected_token):
            raise HTTPException(
                status_code=401, detail="Unauthorized: invalid or missing API token"
            )

    if not psutil.pid_exists(pid):
        raise HTTPException(status_code=404, detail=f"Process {pid} does not exist")

    is_tracked = False
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        if item.get("pid") == pid:
                            is_tracked = True
                            break
        except Exception:
            pass

    if not is_tracked:
        raise HTTPException(
            status_code=403, detail=f"Process {pid} is not a managed AI-DAX workload task"
        )

    from process.affinity import set_process_affinity

    p = psutil.Process(pid)
    success = set_process_affinity(p, payload.cores)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to set CPU affinity (platform or permission constraint)",
        )

    return JSONResponse({"status": "success", "pid": pid, "affinity": payload.cores})


@app.get("/api/scheduler/stats")
def api_scheduler_stats() -> JSONResponse:
    """Alias for /api/bandit-stats."""
    return api_bandit_stats()


@app.get("/api/history")
def api_history(limit: int = 100) -> JSONResponse:
    """Return historical time series data for telemetry charting."""
    rows = read_csv_safe(max_rows=limit)
    return JSONResponse({"history": rows, "count": len(rows)})


@app.post("/api/reset")
def api_reset(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> JSONResponse:
    """Emergency endpoint: releases affinities across all tracked processes."""
    expected_token = os.getenv("AIDAX_API_TOKEN", "")
    if expected_token:
        from security.validation import verify_api_token

        if not verify_api_token(x_api_token, expected_token):
            raise HTTPException(
                status_code=401, detail="Unauthorized: invalid or missing API token"
            )

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
    cpu_percent_overall: float = Field(ge=0.0, le=100.0)
    memory_percent: float = Field(ge=0.0, le=100.0)
    total_decisions: int = Field(ge=0)
    regret: float = Field(ge=0.0)
    voice_query: str = Field(default="", max_length=250)
    language: str = Field(default="English", max_length=50)


@app.post("/api/aizen")
async def api_aizen(payload: TelemetryPayload, request: Request) -> JSONResponse:
    """Aizen AI telemetry insights panel endpoint with strict rate limiting and error masking."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_ai_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "health": "Rate Limit Exceeded",
                "process": f"Max {MAX_AI_REQUESTS_PER_MINUTE} requests/min. Please wait before retrying.",
                "future": "Bandit scheduling is unaffected.",
            },
        )

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
        return JSONResponse(
            {"health": str(val[0])[:200], "process": str(val[1])[:200], "future": str(val[2])[:200]}
        )
    except Exception as e:
        err_str = str(e)
        logger.warning("Aizen inference error: %s", type(e).__name__)
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
                "health": "Aizen Service Notice",
                "process": "AI inference service temporarily unavailable.",
                "future": "Local bandit and telemetry remain fully operational.",
            }
        )


@app.post("/api/jarvis")
async def api_jarvis(payload: TelemetryPayload, request: Request) -> JSONResponse:
    """Multilingual assistant endpoint with input sanitization and rate limiting."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_ai_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"response": "Speech assistant rate limit reached. Please wait a minute."},
        )

    if not API_KEY or not _genai_available:
        return JSONResponse({"response": "Speech assistant offline: missing GEMINI_API_KEY."})

    # Sanitize query input
    clean_query = re.sub(r"[\r\n\t]", " ", payload.voice_query).strip()[:200]
    clean_lang = re.sub(r"[^A-Za-z0-9 -]", "", payload.language).strip()[:30]

    prompt = (
        f"You are Jarvis, an operating system assistant. User says: '{clean_query}'. "
        f"Language: '{clean_lang}'. Current CPU: {payload.cpu_percent_overall}%. "
        f"Respond concisely in '{clean_lang}' exclusively."
    )
    try:
        import google.generativeai as genai

        model = genai.GenerativeModel("gemini-flash-lite-latest")
        resp = await asyncio.to_thread(model.generate_content, prompt)
        return JSONResponse({"response": resp.text.strip()[:500]})
    except Exception as e:
        logger.warning("Jarvis speech error: %s", type(e).__name__)
        return JSONResponse({"response": "Speech assistant temporarily unavailable."})


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
