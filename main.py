"""
AI-DAX Lite: FastAPI Dashboard Backend
======================================
Serves the premium HTML/JS frontend and provides REST + WebSocket endpoints
for live CPU health monitoring and task management.

Endpoints:
  GET  /                  — Serve the static frontend
  GET  /api/live          — Latest scheduler state from CSV
  GET  /api/history       — Last N rows for charting
  POST /api/reset         — Emergency affinity reset
  GET  /api/bandit-stats  — Current bandit parameters + regret + decision breakdown
  WS   /ws/live           — WebSocket pushing updates every 1s
"""

import os
import json
import csv
import asyncio
from io import StringIO
from typing import List, Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI-DAX Lite Dashboard", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE = 'scheduler_log.csv'
PID_FILE = 'pids.txt'
BANDIT_STATS_FILE = 'bandit_stats.json'

# ─────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────

def read_csv_safe(max_rows=300):
    """Read log CSV defensively. Returns list of dicts."""
    rows = []
    try:
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            return rows
        with open(LOG_FILE, 'r') as f:
            content = f.read()
        reader = csv.DictReader(StringIO(content))
        all_rows = list(reader)
        rows = all_rows[-max_rows:]
    except Exception:
        pass
    return rows


def reset_all_affinities():
    """Emergency: releases all tracked processes from specific core assignment."""
    total_cores = os.cpu_count() or 4
    all_cores = list(range(total_cores))
    count = 0
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        pid = data['pid']
                        start_time = data['start_time']
                        p = psutil.Process(pid)
                        if (p.create_time() == start_time and
                                p.username() == psutil.Process().username()):
                            p.cpu_affinity(all_cores)
                            count += 1
                    except Exception:
                        pass
        except FileNotFoundError:
            pass
    return count


def get_system_health():
    """Return system-level CPU health metrics."""
    cpu_percent_per_core = psutil.cpu_percent(percpu=True)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    return {
        'cpu_percent_overall': psutil.cpu_percent(),
        'cpu_percent_per_core': cpu_percent_per_core,
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'cpu_count_physical': psutil.cpu_count(logical=False),
        'cpu_freq_current': cpu_freq.current if cpu_freq else 0,
        'cpu_freq_max': cpu_freq.max if cpu_freq else 0,
        'cpu_freq_min': cpu_freq.min if cpu_freq else 0,
        'memory_total_gb': round(mem.total / (1024**3), 2),
        'memory_used_gb': round(mem.used / (1024**3), 2),
        'memory_percent': mem.percent,
    }


def read_bandit_stats():
    """Read bandit stats JSON atomically written by the scheduler."""
    try:
        if os.path.exists(BANDIT_STATS_FILE):
            with open(BANDIT_STATS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        'total_decisions': 0,
        'heuristic_count': 0,
        'bandit_count': 0,
        'cumulative_regret': 0.0,
    }


# ─────────────────────────────────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────────────────────────────────

@app.get("/api/live")
async def api_live():
    """Latest state from scheduler log + system health."""
    rows = read_csv_safe(max_rows=50)
    if rows:
        # Get the most recent timestamp group
        latest_ts = rows[-1].get('timestamp', '')
        recent = [r for r in rows if r.get('timestamp') == latest_ts]
    else:
        recent = []

    return JSONResponse({
        'processes': recent,
        'system': get_system_health(),
        'bandit': read_bandit_stats(),
    })


@app.get("/api/history")
async def api_history(n: int = 200):
    """Last N rows for charting."""
    rows = read_csv_safe(max_rows=min(n, 500))
    return JSONResponse({'history': rows, 'count': len(rows)})


@app.post("/api/reset")
async def api_reset():
    """Emergency affinity reset."""
    count = reset_all_affinities()
    return JSONResponse({
        'status': 'ok',
        'released': count,
        'message': f'Released affinity constraints for {count} processes.'
    })


@app.get("/api/bandit-stats")
async def api_bandit_stats():
    """Current bandit parameters, cumulative regret, decision breakdown."""
    stats = read_bandit_stats()
    total = stats.get('heuristic_count', 0) + stats.get('bandit_count', 0)
    if total > 0:
        stats['heuristic_pct'] = round(stats['heuristic_count'] / total * 100, 1)
        stats['bandit_pct'] = round(stats['bandit_count'] / total * 100, 1)
    else:
        stats['heuristic_pct'] = 0
        stats['bandit_pct'] = 0
    return JSONResponse(stats)


# ─────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    """Push live updates every 1 second."""
    await websocket.accept()
    try:
        while True:
            rows = read_csv_safe(max_rows=50)
            if rows:
                latest_ts = rows[-1].get('timestamp', '')
                recent = [r for r in rows if r.get('timestamp') == latest_ts]
            else:
                recent = []

            payload = {
                'processes': recent,
                'system': get_system_health(),
                'bandit': read_bandit_stats(),
                'history_tail': read_csv_safe(max_rows=100),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# Static Files & Root
# ─────────────────────────────────────────────────────────────────────

# Mount static directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")
