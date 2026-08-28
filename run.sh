#!/bin/bash
# AI-DAX Lite — Launcher Script
# Runs the workload generator, AI scheduler (LinUCB bandit), and
# FastAPI dashboard frontend together.

set -e

echo "[*] Setting up AI-DAX Lite environment..."

# Create venv if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "[*] Starting Workload Generator..."
python3 workload_generator.py &
WORKLOAD_PID=$!

echo "[*] Starting AI Scheduler (LinUCB Bandit)..."
python3 ai_scheduler.py &
SCHEDULER_PID=$!

# Cleanup handler
function cleanup {
    echo ""
    echo "[*] Handling shutdown. Sending SIGTERM to stop processes safely..."
    kill -TERM $SCHEDULER_PID 2>/dev/null
    kill -TERM $WORKLOAD_PID 2>/dev/null
    echo "[*] Cleanup completed. Exiting..."
    exit
}

trap cleanup EXIT INT TERM

echo "[*] Launching Dashboard (http://localhost:8000)..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Wait to catch termination signals correctly
wait
