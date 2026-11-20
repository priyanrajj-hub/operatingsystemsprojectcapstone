#!/bin/bash
# AI-DAX Lite — Launcher Script
# Runs the workload generator, AI scheduler (LinUCB bandit), and
# FastAPI dashboard frontend together.

set -e

# Change directory to project root if invoked from scripts/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "[*] Setting up AI-DAX Lite environment..."

# Prefer .venv, fallback to venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q -e .
fi

echo "[*] Starting Workload Generator..."
python3 -m aidax.workload &
WORKLOAD_PID=$!

echo "[*] Starting AI Scheduler (LinUCB Bandit)..."
python3 -m aidax.scheduler &
SCHEDULER_PID=$!

# Cleanup handler
function cleanup {
    echo ""
    echo "[*] Handling shutdown. Sending SIGTERM to stop processes safely..."
    kill -TERM $SCHEDULER_PID 2>/dev/null || true
    kill -TERM $WORKLOAD_PID 2>/dev/null || true
    echo "[*] Cleanup completed. Exiting..."
    exit
}

trap cleanup EXIT INT TERM

echo "[*] Launching Dashboard (http://localhost:8000)..."
python3 -m uvicorn aidax.api:app --host 127.0.0.1 --port 8000

# Wait to catch termination signals correctly
wait
