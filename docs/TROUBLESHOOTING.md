# AI-DAX Lite — Troubleshooting Guide

This guide covers common runtime issues, platform constraints, and troubleshooting steps for AI-DAX Lite across Windows, Linux, and macOS.

---

## 1. Process Affinity Errors

### Windows: `PermissionError: [WinError 5] Access is denied`
- **Cause:** Attempting to alter CPU affinity of a process running with elevated administrative privileges or protected system processes (`csrss.exe`, `System`, `services.exe`).
- **Remedy:** AI-DAX only tracks and manipulates worker processes spawned by its own workload generator or unprivileged user processes recorded in `pids.txt`. If you run benchmarks, execute PowerShell or Terminal in normal user mode.

### Linux: `PermissionError: [Errno 1] Operation not permitted`
- **Cause:** Linux kernel requires `CAP_SYS_NICE` or matching EUID to execute `sched_setaffinity(2)` on other processes.
- **Remedy:** Ensure the scheduler runs under the same user UID as the workload generator.

### macOS: `AttributeError: module 'psutil' has no attribute 'cpu_affinity'`
- **Cause:** macOS Mach kernel does not support thread-level or process-level hard CPU affinity.
- **Remedy:** AI-DAX detects macOS automatically and falls back gracefully to non-affinity simulated tracking without raising unhandled exceptions.

---

## 2. Emergency Affinity Reset

If processes were left pinned to specific cores following an abnormal abort or test crash:

### Using the CLI
```powershell
# PowerShell (Windows)
python -m aidax.scheduler --recover

# Bash (Linux)
python3 -m aidax.scheduler --recover
```

### Using the Web Dashboard
Click the **"Reset Affinities"** button in the header of the Process Monitor table on `http://127.0.0.1:8000`.

---

## 3. Hardware Core Topology

### "SIMULATED PARTITION" Warning in Logs
- **Log Message:** `Operating with SIMULATED PARTITION (P-cores=[...], E-cores=[...]) on non-hybrid host.`
- **Meaning:** Your CPU does not have hardware-level heterogeneous cores (e.g. standard AMD Ryzen or older Intel Core without E-cores).
- **Behavior:** AI-DAX partitions logical cores into P-core and E-core pools to allow full algorithmic evaluation and research simulation. This is expected behavior and will not harm performance.

### Linux Hybrid Core Detection
AI-DAX reads Intel sysfs topology from `/sys/devices/cpu_core/cpus` and `/sys/devices/cpu_atom/cpus`. If those nodes do not exist, it falls back to max core frequency analysis under `/sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq`.

---

## 4. Frontend & Telemetry Issues

### Dashboard Shows "DEMO: SIMULATED DATA" Banner
- **Cause:** The frontend dashboard cannot establish a WebSocket connection to `ws://127.0.0.1:8000/ws/live` and REST polling to `http://127.0.0.1:8000/api/live` failed.
- **Checklist:**
  1. Confirm the backend is running: `curl http://127.0.0.1:8000/api/health`
  2. Verify port 8000 is not blocked by Windows Defender Firewall or another service.
  3. Start all services together: `python scripts/start_all.py`

### WebSocket Disconnects Repeatedly
- **Behavior:** The dashboard automatically uses exponential backoff reconnection (1s up to 15s max).
- If deployed on Vercel without a running local tunnel, the frontend runs in explicit simulated preview mode with clear visual indicators.

---

## 5. File System & Concurrency

### Stale `pids.txt` or `bandit_stats.json` Lock
- **Remedy:** AI-DAX utilizes atomic write operations (`atomic_write_text` and `atomic_write_json`) with exponential retry backoff on Windows `PermissionError`. In the event of a hard crash, manually delete temporary files:
  ```powershell
  Remove-Item -Path "tmp*","pids.txt","bandit_stats.json" -ErrorAction SilentlyContinue
  ```

---

## 6. AI Insights (Aizen & Jarvis) Offline

- **Symptoms:** Aizen shows `Aizen Offline (API key not configured)`.
- **Solution:** Provide a valid Google Gemini API key:
  ```powershell
  # Create .env from template
  Copy-Item .env.example .env
  # Set GEMINI_API_KEY=your_key_here
  ```
- **Note:** Offline mode provides deterministic rule-based telemetry analysis without making external network calls.
