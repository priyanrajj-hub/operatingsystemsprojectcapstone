# AI-DAX Lite — REST & WebSocket API Specification

This document provides a comprehensive reference for all HTTP REST and WebSocket telemetry endpoints exposed by the AI-DAX telemetry hub (`src/aidax/api.py`).

## Base URL
```
http://127.0.0.1:8000
```
> [!IMPORTANT]
> By default, the server binds strictly to the loopback interface `127.0.0.1` to prevent unauthorized external network access.

---

## Authentication
Sensitive administrative endpoints require authentication via the `X-API-Token` HTTP header when `AIDAX_API_TOKEN` is configured in the environment:

```http
X-API-Token: <your-token>
```
If `AIDAX_API_TOKEN` is set and the header is missing or incorrect, the server responds with:
`401 Unauthorized: invalid or missing API token`.

Protected endpoints:
- `POST /api/scheduler/start`
- `POST /api/scheduler/stop`
- `POST /api/process/{pid}/affinity`
- `POST /api/reset`

---

## 1. System & Health Endpoints

### `GET /api/health`
Returns the operational health status of the API server.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "version": "0.3.0",
  "timestamp": 1700000000.0,
  "service": "ai-dax-lite"
}
```

---

### `GET /api/system`
Returns real-time operating system telemetry, CPU utilisation, memory consumption, frequency, and discovered topology summary.

**Response `200 OK`**:
```json
{
  "cpu_percent_overall": 24.5,
  "cpu_percent_per_core": [35.2, 12.0, 40.1, 8.5],
  "memory_percent": 42.8,
  "memory_used_gb": 6.8,
  "memory_total_gb": 16.0,
  "cpu_count_logical": 24,
  "cpu_count_physical": 16,
  "cpu_freq_current": 3200.0,
  "cpu_freq_max": 5400.0,
  "uptime_seconds": 128450.0,
  "topology_status": "windows_kernel32_efficiency_class",
  "is_heterogeneous": true,
  "p_cores": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  "e_cores": [16, 17, 18, 19, 20, 21, 22, 23]
}
```

---

### `GET /api/hardware`
Returns detailed hardware core classification detected via native platform APIs (Win32 `GetLogicalProcessorInformationEx` on Windows, sysfs on Linux).

**Response `200 OK`**:
```json
{
  "total_logical_cores": 24,
  "total_physical_cores": 16,
  "is_heterogeneous": true,
  "detection_method": "windows_kernel32_efficiency_class",
  "confidence": 1.0,
  "p_cores": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  "e_cores": [16, 17, 18, 19, 20, 21, 22, 23],
  "cores": [
    {
      "core_id": 0,
      "physical_core_id": 0,
      "core_type": "P-core",
      "max_frequency_mhz": 0.0,
      "numa_node": 0,
      "is_smt": true
    }
  ]
}
```

---

## 2. Process & Telemetry Endpoints

### `GET /api/processes`
Lists all managed benchmark workload processes registered in `pids.txt` along with live resource consumption and current core affinity masks.

**Response `200 OK`**:
```json
{
  "processes": [
    {
      "pid": 14208,
      "name": "python.exe",
      "type": "heavy",
      "cpu_percent": 84.5,
      "memory_percent": 0.4,
      "status": "running",
      "current_affinity": [0, 1, 2, 3]
    }
  ],
  "count": 1
}
```

---

### `GET /api/live`
Returns the most recent cycle decisions for active processes from the CSV log file.

**Response `200 OK`**:
```json
{
  "processes": [
    {
      "timestamp": "1700000010.5",
      "pid": "14208",
      "true_type": "heavy",
      "action": "P-core",
      "decision_source": "bandit",
      "cpu_percent": "85.2",
      "vol_ctx_rate": "12.0",
      "invol_ctx_rate": "15.0",
      "confidence_ucb": "1.420",
      "reward": "-0.1500"
    }
  ],
  "count": 1
}
```

---

### `GET /api/history?limit=100`
Returns historical decision time series data (up to `limit` records) for frontend charting.

---

### `GET /api/telemetry`
Consolidated endpoint providing atomic snapshots of system health and bandit performance metrics.

**Response `200 OK`**:
```json
{
  "system": { "cpu_percent_overall": 24.5, ... },
  "bandit": { "total_decisions": 120, "cumulative_regret": 2.45, ... },
  "timestamp": 1700000020.1
}
```

---

## 3. Scheduler & Affinity Control Endpoints

### `GET /api/scheduler/status`
Reports scheduler daemon operational state, active workload count, and log presence.

**Response `200 OK`**:
```json
{
  "status": "running",
  "tracked_processes": 4,
  "log_file_present": true,
  "stats_file_present": true
}
```

---

### `POST /api/scheduler/start`
*(Requires `X-API-Token` if enabled)*  
Signals scheduler startup and activates tracking.

---

### `POST /api/scheduler/stop`
*(Requires `X-API-Token` if enabled)*  
Signals scheduler termination and initiates graceful process release.

---

### `POST /api/process/{pid}/affinity`
*(Requires `X-API-Token` if enabled)*  
Safely updates the CPU core affinity mask of a specific process.

> [!CAUTION]
> Defense against Confused Deputy: The target PID must exist in `pids.txt` (managed workload registry). Calling this endpoint with arbitrary system PIDs returns `403 Forbidden`.

**Request Body**:
```json
{
  "cores": [0, 1, 2, 3]
}
```

**Response `200 OK`**:
```json
{
  "status": "success",
  "pid": 14208,
  "affinity": [0, 1, 2, 3]
}
```

---

### `POST /api/reset`
*(Requires `X-API-Token` if enabled)*  
Emergency fail-safe endpoint: resets affinities of all tracked processes across all available logical cores.

**Response `200 OK`**:
```json
{
  "status": "success",
  "released_processes": 4,
  "message": "Successfully cleared affinities on 4 process(es)."
}
```

---

## 4. Bandit Statistics

### `GET /api/bandit-stats` (and alias `GET /api/scheduler/stats`)
Returns cumulative exploration vs exploitation decision counts, percentage breakdown, and regret metrics.

**Response `200 OK`**:
```json
{
  "heuristic_count": 20,
  "bandit_count": 180,
  "total_decisions": 200,
  "heuristic_pct": 10.0,
  "bandit_pct": 90.0,
  "cumulative_regret": 4.12,
  "alpha_reward": 0.7,
  "beta_reward": 0.3
}
```

---

## 5. WebSocket Telemetry Stream

### `WebSocket /ws/live`
Streams a live telemetry frame every second containing:
- Current process telemetry
- Host system health
- Bandit decision statistics
- Historical tail for continuous graph rendering

**Frame Structure**:
```json
{
  "processes": [ ... ],
  "system": { ... },
  "bandit": { ... },
  "history_tail": [ ... ]
}
```
