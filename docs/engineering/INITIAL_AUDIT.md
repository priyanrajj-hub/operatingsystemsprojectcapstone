# AI-DAX Initial Codebase & Engineering Audit

**Audit Date:** 2026-11-20  
**Auditor:** Staff Software Engineer / Systems & Security Lead  
**Branch:** `fix/code-review-pass`  
**Platform:** Windows 11 AMD64 (Primary developer workstation) / Ubuntu Linux (Research deployment target)  
**Python Runtime:** 3.13.7 (64-bit)

---

## 1. Executive Summary & Baseline Metrics

The AI-DAX Lite codebase was audited across all Python source modules, frontend assets, configuration templates, evaluation harnesses, and shell scripts.

### Baseline Environment
- **OS Platform:** Windows-11-10.0.26320-SP0 AMD64
- **Hardware Profile:** 24 Logical CPUs, 16 Physical Cores (Intel hybrid architecture)
- **`psutil.cpu_affinity` Support:** Supported on Windows (`[0..23]`) and Linux; unsupported on macOS (raises `AttributeError`).
- **Initial Test Suite:** 59 passed in 12.68s.
- **Initial Mypy Status:** 55 files passing in `src/`; duplicate package name error when running `mypy src tests scripts api` due to `api/__init__.py`.
- **Initial Ruff Status:** Clean formatting across core packages.

---

## 2. Suspected Bugs & Technical Debt Audit Matrix

| ID | Component / File | Problem Description | Severity | Status | Reproduction / Evidence | Proposed Correction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S1** | `README.md`, startup | `python x.py &` in PowerShell fails to background processes. | Major | **Confirmed** | Running `python main.py &` in PowerShell triggers command syntax error or runs synchronously. | Create `scripts/start_all.py` / `python -m aidax.run` with subprocess management and SIGINT cleanup; fix PowerShell instructions in README. |
| **S2** | `src/aidax/scheduler.py`, `src/persistence/checkpoints.py` | Leaked `tmp*` file artifacts on disk due to unhandled `PermissionError` on Windows during `os.replace`. | Major | **Confirmed** | Workspace contained >150 leftover `tmp*.json` files. | Implement atomic file replacement with bounded exponential retry and guaranteed tempfile cleanup in `finally:`. |
| **S3** | `src/aidax/scheduler.py`, `src/hardware/` | Naive core partitioning (first half = P, second half = E) without checking actual Linux sysfs hybrid nodes (`/sys/devices/cpu_core/cpus`, `/sys/devices/cpu_atom/cpus`). | Major | **Confirmed** | `detect_cores()` splits cores 50/50 when sysfs files are absent; ignores modern sysfs paths and lacks "SIMULATED PARTITION" warning. | Integrate `src/hardware/detection.py` with mockable fallback, check sysfs cpu_core/cpu_atom, and label simulated partitions explicitly. |
| **S4** | `src/aidax/scheduler.py` | Cold-start threshold (20 decisions per PID) locks short-lived workloads into heuristic mode forever; resets improperly on PID churn. | Critical | **Confirmed** | Line 468 checks `pid_decision_count[pid] <= 20`. Under PID churn where tasks last 10s, bandit is never engaged ($0\%$ adaptive decisions). | Implement global warmup counter and per-PID warm start; recheck creation time on PID reuse. |
| **S5** | `src/aidax/scheduler.py` | Context vector feedback: `current_core_assignment` is the bandit's own previous action, creating feedback autocorrelation. | Minor | **Confirmed** | Line 439 queries current affinity and feeds it directly into feature $x_4$. | Test feature significance; lag or decorrelate feature input. |
| **S6** | `src/aidax/scheduler.py` | Circular reward and counterfactual regret estimation: unselected action reward is evaluated using the selected action's measured context switch rate. | Critical | **Confirmed** | Lines 460-464 evaluate `r_a` for both arms using the same observed `invol_rate`, artificially favoring E-cores. | Separate observed reward from counterfactual oracle; only compute true regret in simulated environments with valid counterfactuals. |
| **S7** | `src/aidax/scheduler.py` | Explicit $O(d^3)$ `np.linalg.inv(self.A)` matrix inversion computed on every update; missing NaN/Inf guards. | Major | **Confirmed** | Line 85 calls `np.linalg.inv(self.A)`. Potential numerical instability under collinear features. | Maintain inverse via Sherman-Morrison rank-1 update or Cholesky decomposition; add input sanitization guards against NaN/Inf. |
| **S8** | `src/aidax/scheduler.py` | Unbounded dictionary growth for dead PIDs (`self.history`, `self.pending`, `self.pid_decision_count`), causing memory leaks over long runs. | Major | **Confirmed** | No dictionary eviction mechanism exists when a PID exits. | Prune dead PIDs from internal state tables at the end of each scheduling cycle. |
| **S9** | `src/aidax/scheduler.py`, `src/aidax/api.py` | Shutdown signal handling on Windows does not guarantee affinity restoration on unexpected termination; no `--recover` CLI command. | Major | **Confirmed** | `signal.SIGTERM` is not raised on Windows console Ctrl+C; missing standalone affinity recovery tool. | Add `atexit` hooks, Windows console control handler, and implement `--recover` CLI flag to reset all managed PIDs. |
| **S10** | `scripts/legacy/dashboard.py` | Streamlit dashboard schema mismatch: looks for `latency_ms`, `mode`, `classification` which do not exist in `scheduler_log.csv`. | Minor | **Confirmed** | Streamlit app crashes with `KeyError` on reading `scheduler_log.csv`. | Align schema with canonical `CSV_HEADER` or designate FastAPI static UI as sole source of truth. |
| **S11** | `static/app.js`, `static/index.html` | Frontend generates synthetic `Math.random()` telemetry when backend is disconnected without clear user notification. | Major | **Confirmed** | Lines 434-488 generate fake CPU percentages, PIDs, and regret without warning the user. | Remove fake telemetry; add prominent `"DEMO: SIMULATED DATA"` indicator when running disconnected or on cloud serverless. |
| **S12** | `src/aidax/evaluate.py`, `src/aidax/analysis.py` | Evaluation harness process reaping and paired t-test handling of zero-variance or unequal sample counts. | Major | **Confirmed** | If a worker process crashes, child processes may orphan; paired t-test warns on near-identical data. | Implement robust worker cleanup with `psutil.wait_procs()`, validate results schema, and guard paired t-tests. |
| **S13** | `src/aidax/` | Inconsistent logging; mixed `print()` statements and swallowed exceptions in legacy scripts. | Minor | **Confirmed** | Legacy scripts in `scripts/legacy/` had syntax errors (`compute_final.py`). | Replace `print()` with structured logging; eliminate bare `except:`. |
| **S14** | `src/aidax/scheduler.py` | Magic numbers in CLI and reward calculations hardcoded without configuration schema validation. | Minor | **Confirmed** | Hyperparameters (0.7, 0.3, 1000.0) duplicated across CLI arguments and settings. | Centralize via `src.core.config.settings` with bounds checking. |

---

## 3. Detailed Component Review

### 3.1 LinUCB Numerics & Stability
In `src/aidax/scheduler.py`:
- `LinUCBArm` performs `np.linalg.inv(self.A)` on every cycle when dirty. For dimension $d=5$, direct inversion is small, but rank-1 updates $A_{t+1} = A_t + x x^T$ allow exact $O(d^2)$ maintenance of $A^{-1}$ via the Sherman-Morrison formula:
  $$A_{t+1}^{-1} = A_t^{-1} - \frac{A_t^{-1} x x^T A_t^{-1}}{1 + x^T A_t^{-1} x}$$
- Updating $A^{-1}$ incrementally eliminates matrix inversion errors, guarantees positive-definiteness when initialized with $\lambda I$, and prevents numerical drift.

### 3.2 State Eviction & Memory Leaks
In `src/aidax/scheduler.py`:
- `self.history`, `self.pending`, and `self.pid_decision_count` accumulate keys indefinitely. In production with thousands of short-lived processes, this table grows unbounded.
- Remedy: Query active PIDs from `self.get_active_pids()`; prune keys from dictionaries whose PIDs are no longer active and have no pending rewards.

### 3.3 Atomic File Writing & Windows Locking
In `src/aidax/scheduler.py`:
- `_write_bandit_stats()` and `_write_csv_rows()` use `tempfile.mkstemp()`. On Windows, antivirus software and concurrent readers periodically hold open handles to `scheduler_log.csv`, causing `os.replace` to fail with `PermissionError`.
- Remedy: Provide an `atomic_replace()` helper that retries with exponential backoff and always unlinks temporary files in a `finally` block.
