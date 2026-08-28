# AI-DAX Lite: Adaptive CPU Governor with LinUCB Contextual Bandit

A **user-space CPU scheduling simulator** that routes processes to Performance (P) or Efficiency (E) cores using a **LinUCB contextual bandit** that learns from measured outcomes — not hand-written rules.

> **Research contribution**: Unlike static classifiers that imitate heuristics, AI-DAX Lite implements a closed-loop system where the bandit's reward signal comes from *actual* measured involuntary context switches and an energy cost proxy. This makes the routing policy genuinely adaptive, not just a supervised imitation of a hand-written rule.

## Architecture

```
┌──────────────┐     ┌───────────────────────┐     ┌────────────────┐
│   Workload   │     │    AI Scheduler       │     │   Dashboard    │
│  Generator   │────▶│  (LinUCB Bandit)      │────▶│  (FastAPI +    │
│  (pids.txt)  │     │                       │     │   HTML/JS)     │
│              │     │  Context → Action     │     │                │
│  Heavy/Light │     │  Measure → Reward     │     │  localhost:8000│
│  workers     │     │  Update → Learn       │     │                │
└──────────────┘     └───────────────────────┘     └────────────────┘
```

## LinUCB Bandit Formulation

### Context Vector (per PID, per cycle)

```
x = [cpu_percent, voluntary_ctx_rate, involuntary_ctx_rate,
     time_since_last_switch, current_core_assignment]
```

Features are online-normalised using Welford's algorithm.

### Actions

- **Action 0**: Route to P-cores (high-performance)
- **Action 1**: Route to E-cores (low-power)

### Reward Signal

```
R_t = -(α · normalised_involuntary_ctx_switches + β · energy_proxy_cost)
```

Where:

- `energy_proxy_cost = 1.0` for P-core, `0.3` for E-core (P-cores draw ~3× power on Intel hybrid architectures; this proxy is standard when direct wattage metering is unavailable)
- `α = 0.7`, `β = 0.3` (configurable via CLI for sensitivity sweeps)
- The reward is measured from the **actual outcome** of the previous cycle's routing decision, not from any heuristic label

### UCB Action Selection

```
score_a = x^T θ_a + α_explore · √(x^T A_a^{-1} x)
```

Where `A_a` and `b_a` are updated online: `A ← A + xx^T`, `b ← b + r·x` (Li et al., WWW 2010).

### Cold Start

The heuristic (`cpu > 20% && vol_rate < 500 → Heavy`) serves as a fallback for the first 20 decisions per PID before the bandit has enough data to make informed choices.

## Quick Start

### Requirements

```bash
pip install -r requirements.txt
```

### Run Dashboard Locally

```bash
# Linux/Mac
bash run.sh

# Windows (PowerShell)
python workload_generator.py &
python ai_scheduler.py &
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open **<http://localhost:8000>**.

### Run Evaluation Harness

```bash
# Full 4-condition, 5-trial evaluation (takes ~25 minutes with 60s/condition)
python evaluate.py --duration 60 --trials 5

# Quick test (10s, 2 trials)
python evaluate.py --duration 10 --trials 2

# View results
python results_summary.py
```

## Evaluation Methodology

The evaluation harness (`evaluate.py`) compares four scheduling conditions:

| Condition        | Description                                          |
|-----------------|------------------------------------------------------|
| `baseline_cfs`  | No affinity calls — pure OS CFS scheduling           |
| `static_naive`  | Fixed rule: Heavy→P-core, Light→E-core, no learning  |
| `heuristic_only`| Heuristic classification, learning disabled           |
| `bandit_adaptive`| Full LinUCB with measured-reward updates             |

Each condition runs on the **same workload mix** for a configurable duration (default 60s), repeated 5 trials. Metrics collected per process:

- Mean/Median/P95 involuntary context switches
- Mean CPU utilisation
- Jain's Fairness Index: `J = (Σx_i)² / (n · Σx_i²)`

Statistical comparison: **paired t-test** (`scipy.stats.ttest_rel`) between `bandit_adaptive` and each baseline (`results_summary.py`).

## Methodology Paragraph (Paper-Ready)

> We evaluate the AI-DAX Lite system's LinUCB contextual bandit routing policy using a four-condition within-subjects experimental design. Mixed workloads consisting of two CPU-bound and two I/O-bound processes are executed under each scheduling condition—unmanaged CFS baseline, static heuristic routing, heuristic-only classification, and the full LinUCB bandit—for 60 seconds per trial over five independent repetitions. The bandit formulates each routing decision as a contextual bandit problem, where the context vector comprises normalised CPU utilisation, voluntary and involuntary context switch rates, time since last core reassignment, and current core assignment. The reward signal R_t = -(0.7 · normalised involuntary context switches + 0.3 · energy proxy cost) is computed from measured process-level metrics one scheduling cycle after each routing action, ensuring the model learns from actual system responses rather than proxy labels. We report mean ± standard deviation across trials and assess statistical significance using the paired t-test (α = 0.05) between the bandit-adaptive condition and each baseline. Resource fairness is quantified using Jain's Fairness Index computed over per-process CPU time allocations.

## Files

| File | Description |
| ------ | ------------- |
| `ai_scheduler.py` | LinUCB contextual bandit CPU scheduler |
| `workload_generator.py` | Configurable workload spawner (infinite/finite mode) |
| `evaluate.py` | Four-condition evaluation harness |
| `results_summary.py` | Statistical analysis (mean±std, t-tests, fairness) |
| `main.py` | FastAPI backend (REST + WebSocket) |
| `static/` | Premium dashboard frontend (HTML/CSS/JS) |
| `run.sh` | Launcher script |

## Safety Mechanisms

All original safety mechanisms are preserved:

- **PID-reuse guard**: Cross-checks `create_time()` against recorded spawn time
- **Atomic logging**: Writes via `tempfile` + `os.replace()` (no partial reads)
- **Graceful shutdown**: SIGINT/SIGTERM handler resets all affinities
- **Non-root operation**: Uses `psutil.cpu_affinity()` (user-space only)
- **Emergency reset**: Dashboard button to instantly release all affinity constraints

## License

Research prototype — academic use.
