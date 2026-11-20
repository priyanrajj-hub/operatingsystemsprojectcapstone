# AI-DAX Lite — Technical Audit Report

**Date:** November 20, 2026  
**Auditor:** Principal Systems Architect & Senior Security Engineer  
**Scope:** Full repository audit of AI-DAX Lite (Adaptive Intelligence for Dynamic Allocation and Execution)

---

## 1. Complete Data Flow Tracing

The complete system pipeline traverses the following 10 stages:

```mermaid
flowchart TD
    subgraph S1["Stage 1: Workload Generation"]
        WG["Workload Generator\n(src/aidax/workload.py)"] -->|spawns| CP["Child Worker Processes\n(Heavy prime compute & Light I/O)"]
    end

    subgraph S2["Stage 2: Process Registration"]
        CP -->|records PID + create_time| PR["Atomic Process Registry\n(pids.txt / ProcessRegistry)"]
    end

    subgraph S3["Stage 3: Hardware Topology Detection"]
        HW["Hardware Detection\n(src/hardware/)"] -->|queries sysfs / Win32| TOP["Topology Model\n(P-cores, E-cores, Frequencies)"]
    end

    subgraph S4["Stage 4: Telemetry Sampling"]
        PR & TOP -->|reads / samples| TS["Telemetry Sampler\n(psutil CPU%, ctx switches)"]
    end

    subgraph S5["Stage 5: Feature Normalization & Context Vector"]
        TS -->|raw context x_t| WS["Online Scaler\n(Welford running variance)"]
    end

    subgraph S6["Stage 6: LinUCB Decision-Making"]
        WS -->|normalized context| LIN["LinUCB Bandit\n(Sherman-Morrison O(d²) update)"]
    end

    subgraph S7["Stage 7: Process Affinity Dispatch"]
        LIN -->|action a_t (P or E core)| AFF["psutil.cpu_affinity\n(Platform Guarded)"]
    end

    subgraph S8["Stage 8: Reward Attribution & Regret Tracking"]
        AFF -->|delta context switches| RWD["Reward Engine & Regret Tracker\n(Observed vs Estimated Regret)"]
    end

    subgraph S9["Stage 9: Persistence & State Logging"]
        RWD -->|atomic append| LOG["scheduler_log.csv & bandit_stats.json\nSQLite (src/persistence/)"]
    end

    subgraph S10["Stage 10: API, WebSocket & Dashboard"]
        LOG -->|reads state| API["FastAPI Backend\n(127.0.0.1:8000, WebSockets)"]
        API -->|broadcasts events| UI["Glassmorphic UI\n(Real Telemetry / Safe DOM)"]
    end
```

---

## 2. Identified Vulnerabilities and Deficiencies (Initial Baseline vs. Target Fixes)

### 2.1 Algorithmic Correctness (LinUCB)
1. **Matrix Inversion Complexity:** Original prototype utilized `np.linalg.inv(A)` on every scheduling cycle ($O(d^3)$ per arm). On multi-threaded workloads with frequent decisions, this introduced significant scheduling latency.
   - *Resolution:* Implemented Sherman-Morrison rank-1 update ($O(d^2)$ complexity) maintaining $A^{-1}$ incrementally:
     $$A^{-1} \leftarrow A^{-1} - \frac{A^{-1} x x^T A^{-1}}{1 + x^T A^{-1} x}$$
2. **Feature Scale Drift:** The feature normalizer previously drifted continuously, distorting historical weights stored in $b = \sum r_t x_t$.
   - *Resolution:* Feature scaling stabilized via warm-up calibration, numerical bounds checks ($x \in [-5, 5]$), and NaN/Inf guards.
3. **Reward Attribution Delay:** Context switch rate was measured immediately without accounting for process scheduling delay, leading to credit assignment noise.
   - *Resolution:* Explicit timestamping and pending action queue (`pending[pid] = (action, context, timestamp)`) with per-PID attribution.

### 2.2 Security & Operational Integrity
1. **Network Exposure & Missing Authentication:** Original prototype bound to `0.0.0.0` with unauthenticated `/api/reset` and WebSocket endpoints, allowing unauthorized clients on the LAN to modify CPU affinity.
   - *Resolution:* Default host bound to `127.0.0.1`. Added API token authorization (`X-API-Token`), CORS restrictions without wildcard credentials, and rate limiters on AI endpoints.
2. **Confused Deputy PID Attack:** Any client could pass arbitrary PIDs to pin or starve sensitive system processes (`csrss.exe`, `System`).
   - *Resolution:* PID ownership verification ensures only managed child processes created by the workload generator can be modified.
3. **File System Race Conditions & Tempfile Leaks:** File-based IPC (`pids.txt` and `bandit_stats.json`) used uncoordinated write operations, causing Windows `PermissionError` and orphan `tmp*` files.
   - *Resolution:* Implemented `src/core/fs.py` with atomic write operations, exponential retry backoff, and guaranteed tempfile cleanup in `finally:` blocks.

### 2.3 Hardware & Topology Assumptions
1. **Hardcoded Core Partitions:** Original code assumed fixed 24 cores or arbitrary core splits, failing on AMD Ryzen, 4-core, or 8-core CPUs.
   - *Resolution:* Platform-aware detection using Linux `/sys/devices/cpu_core/cpus` and `/sys/devices/cpu_atom/cpus`, Windows processor topology APIs, and explicit `SIMULATED PARTITION` labeling on homogeneous systems.
2. **macOS Incompatibility:** Calling `psutil.Process().cpu_affinity()` on macOS crashes with `AttributeError`.
   - *Resolution:* Platform guards in `src/process/affinity.py` identify macOS and log clear operational notifications.

### 2.4 Frontend Telemetry Truthfulness
1. **Fabricated Operational Telemetry:** `startDemoSimulation()` in `app.js` used `Math.random()` to generate fake CPU, memory, core utilization, and PIDs (`1024`, `2048`, `3012`, `4056`).
   - *Resolution:* Production dashboard renders exclusively actual backend telemetry. Simulated data is strictly quarantined behind an explicit **"DEMO MODE — SIMULATED DATA"** banner.
2. **DOM XSS Vulnerability:** Table rows were constructed using unescaped string concatenation in `innerHTML`.
   - *Resolution:* Replaced with safe DOM manipulation (`replaceChildren()` and `document.createElement()`) with text node binding.

---

## 3. Dependency & Codebase Inventory

### 3.1 Core Production Modules (`src/`)
- `src/aidax/`: Backward-compatible application entry points (`scheduler.py`, `workload.py`, `api.py`, `evaluate.py`, `analysis.py`).
- `src/core/`: Configuration via Pydantic v2 settings, atomic file system routines, and exception taxonomy.
- `src/hardware/`: Platform detection (`linux.py`, `windows.py`, `topology.py`).
- `src/process/`: Process supervisory controls, affinity guards, and PID lifecycle tracking.
- `src/scheduler/`: LinUCB bandit, Sherman-Morrison rank-1 engine, regret tracking, and reward functions.
- `src/persistence/`: Async SQLAlchemy ORM, SQLite telemetry database, and checksummed state checkpoints.
- `src/telemetry/`: Psutil metrics collector and Pydantic schemas.
- `src/security/`: Secret masking, API token verification, and rate limiting.

### 3.2 Legacy Scripts (`scripts/legacy/`)
All one-off, duplicate, and legacy scripts were moved to `scripts/legacy/` via `git mv`:
- `compute_final.py` & `compute_safe.py`
- `format_clean.py` & `format_results.py`
- `parse_log.py` & `parse_log2.py`
- `check_health.py` & `check_topology.sh`
- `dashboard.py` (Streamlit analytics interface)

---

## 4. Initial Baseline vs. Verified Metrics

| Quality Criterion | Initial Repository State | Current Verified State |
| :--- | :--- | :--- |
| Automated Pytest Tests | 0 | **75 passed** (100% pass rate) |
| Core Package Coverage | 0% | **55%** |
| Ruff Lint Violations | 20+ issues | **0 errors** (87 files checked) |
| Mypy Type Violations | Unconfigured | **0 errors** (73 files checked) |
| Leaked Credentials | Potential exposure | **0 detected** (Gitleaks, Trufflehog, Semgrep) |
| Process Reaping | Leaked zombie workers | **100% reaped** via `psutil.wait_procs` |
