"""
AI-DAX Lite: Legacy Streamlit Telemetry Dashboard
==================================================
NOTE: The primary supported user interface is the FastAPI + Static Web Dashboard
hosted at http://127.0.0.1:8000. This Streamlit dashboard is preserved as a legacy
standalone tool and updated to match the canonical telemetry schema.
"""

from __future__ import annotations

import json
import os
import time

import pandas as pd
import psutil
import streamlit as st

st.set_page_config(page_title="AI-DAX Lite Legacy Dashboard", layout="wide", initial_sidebar_state="expanded")

st.title("AI-DAX Lite: Telemetry Monitor (Legacy Streamlit)")
st.info("Primary UI: FastAPI + HTML5 Dashboard at http://127.0.0.1:8000")

LOG_FILE = "scheduler_log.csv"
PID_FILE = "pids.txt"


def reset_all_affinities() -> int:
    """Releases all tracked processes from any specific core assignment."""
    total_cores = os.cpu_count() or 4
    all_cores = list(range(total_cores))
    count = 0
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        pid = data["pid"]
                        start_time = data["start_time"]
                        p = psutil.Process(pid)
                        if p.create_time() == start_time and hasattr(p, "cpu_affinity"):
                            p.cpu_affinity(all_cores)
                            count += 1
                    except Exception:
                        pass
        except Exception:
            pass
    return count


st.sidebar.header("Safety Controls")
if st.sidebar.button("Emergency Reset (All Cores)"):
    reset_count = reset_all_affinities()
    st.sidebar.success(f"Released affinity constraints for {reset_count} processes.")

placeholder = st.empty()

try:
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        placeholder.warning("Waiting for telemetry data... (Ensure aidax.scheduler is running)")
    else:
        df = pd.read_csv(LOG_FILE)
        if df.empty:
            placeholder.warning("Telemetry file is currently empty.")
        else:
            recent_ts = df["timestamp"].max()
            recent = df[df["timestamp"] == recent_ts]

            col1, col2, col3 = st.columns(3)
            monitored = len(recent["pid"].unique()) if not recent.empty else 0
            mean_cpu = recent["cpu_percent"].mean() if not recent.empty else 0.0
            bandit_decisions = len(recent[recent["decision_source"] == "bandit"]) if not recent.empty else 0

            col1.metric("Active Monitored Tasks", monitored)
            col2.metric("Mean CPU Utilization", f"{mean_cpu:.1f}%")
            col3.metric("Bandit Routed Count", bandit_decisions)

            st.subheader("Live Process Telemetry")
            if not recent.empty:
                display_cols = [
                    c
                    for c in [
                        "pid",
                        "true_type",
                        "action",
                        "assigned_cores",
                        "decision_source",
                        "cpu_percent",
                        "reward",
                    ]
                    if c in recent.columns
                ]
                st.dataframe(recent[display_cols], use_container_width=True, hide_index=True)

            if "timestamp" in df.columns and "cpu_percent" in df.columns:
                st.subheader("Recent CPU Load Time Series")
                st.line_chart(df.tail(100).set_index("timestamp")["cpu_percent"])

except Exception as e:
    placeholder.error(f"Error reading telemetry: {e}")
