import streamlit as st
import pandas as pd
import time
import os
import psutil
import json

st.set_page_config(page_title="AI-DAX Lite Dashboard", layout="wide", initial_sidebar_state="expanded")

st.title("AI-DAX Lite: User-Space CPU Governor")

LOG_FILE = 'scheduler_log.csv'
PID_FILE = 'pids.txt'

def reset_all_affinities():
    """Emergency boundary function: Releases all tracked processes from any specific core assignment."""
    total_cores = os.cpu_count() or 4
    all_cores = list(range(total_cores))
    count = 0
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    pid = data['pid']
                    start_time = data['start_time']
                    p = psutil.Process(pid)
                    # Safety check before lifting affinity constraint
                    if p.create_time() == start_time and p.username() == psutil.Process().username():
                        p.cpu_affinity(all_cores)
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, json.JSONDecodeError, AttributeError):
                    pass
    return count

st.sidebar.header("Safety Controls")
st.sidebar.write("If the AI behaves erratically, use this fallback to restore default OS scheduler freedom.")
if st.sidebar.button("Emergency Reset (All Cores)"):
    reset_count = reset_all_affinities()
    st.sidebar.success(f"Released affinity constraints for {reset_count} processes.")

placeholder = st.empty()

while True:
    try:
        # Defensive check against empty/missing file on first startup
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            with placeholder.container():
                st.warning("Waiting for data stream... (Ensure ai_scheduler.py is running)")
            time.sleep(1)
            continue
            
        df = pd.read_csv(LOG_FILE)
        if df.empty:
            continue
            
        with placeholder.container():
            col1, col2, col3 = st.columns(3)
            
            recent = df[df['timestamp'] == df['timestamp'].max()]
            
            mean_latency = df['latency_ms'].mean()
            mode = recent['mode'].iloc[0] if not recent.empty else "N/A"
            monitored = len(recent['pid'].unique()) if not recent.empty else 0
            
            col1.metric("Monitored Processes", monitored)
            col2.metric("Mean ML Inference Latency", f"{mean_latency:.2f} ms")
            col3.metric("Current Decision Engine", mode)
            
            st.subheader("Live Process Table")
            if not recent.empty:
                display_df = recent[['pid', 'true_type', 'classification', 'assigned_cores', 'confidence', 'cpu_percent']]
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
            st.subheader("CPU Load History (P-Cores vs E-Cores Equivalent)")
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            # Plot the average CPU % of heavy tasks (routed to P-Cores) vs Light tasks (routed to E-Cores)
            chart_data = df.groupby(['datetime', 'classification'])['cpu_percent'].mean().unstack().fillna(0)
            if not chart_data.empty:
                st.line_chart(chart_data)
                
    except pd.errors.EmptyDataError:
        # Gracefully handle if read during a highly unlikely mid-atomic rotation
        pass 
    except FileNotFoundError:
        pass
    except Exception as e:
        # Avoid crashing the UI on other unexpected artifacts
        pass
        
    time.sleep(1)
