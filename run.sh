#!/bin/bash

echo "[*] Setting up AI-DAX Lite environment..."

# Enforce clean environment using Python standard venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "[*] Starting Workload Generator..."
python3 workload_generator.py &
WORKLOAD_PID=$!

echo "[*] Starting AI Scheduler..."
python3 ai_scheduler.py &
SCHEDULER_PID=$!

# Ensures we don't leave orphaned throttled processes if user hits Ctrl+C
function cleanup {
    echo ""
    echo "[*] Handling shutdown. Sending SIGTERM to stop processes safely..."
    # A SIGTERM triggers the Python-side internal signal handlers (resets affinity, cleans pids.txt)
    kill -TERM $SCHEDULER_PID 2>/dev/null
    kill -TERM $WORKLOAD_PID 2>/dev/null
    echo "[*] Cleanup completed. Exiting..."
    exit
}

trap cleanup EXIT INT TERM

echo "[*] Launching Streamlit Dashboard..."
streamlit run dashboard.py

# Wait to catch termination signals correctly
wait
