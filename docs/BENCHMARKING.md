# AI-DAX Lite — Empirical Evaluation & Benchmarking Protocol

This document defines the rigorous experimental benchmarking methodology, baseline conditions, metric definitions, and statistical significance testing procedures for evaluating AI-DAX Lite.

---

## 1. Experimental Conditions

The evaluation suite (`src/aidax/evaluate.py`) evaluates scheduling strategies across identical workloads and cycle budgets.

| Condition Key | Strategy Name | Affinity Mask | Adaptive Learning? | Description |
|---|---|---|:---:|---|
| `baseline_cfs` | OS Default (CFS / Windows NT) | All logical cores | No | Pure operating system scheduling without affinity pinning. |
| `p_core_only` | Performance Saturated | P-cores exclusively | No | Pins all workload threads strictly to high-frequency P-cores. |
| `e_core_only` | Efficiency Saturated | E-cores exclusively | No | Pins all workload threads strictly to low-power E-cores. |
| `static_naive` | Static Heuristic Partition | Fixed P/E mapping | No | Compute-heavy threads pinned to P-cores; I/O threads pinned to E-cores. |
| `heuristic_only` | Dynamic Threshold Rule | Re-evaluated per cycle | No | Reclassifies affinity each cycle based on static context thresholds. |
| `bandit_adaptive` | AI-DAX Contextual Bandit | Dynamic LinUCB | **Yes** | Online LinUCB learning with Sherman-Morrison updates and feature scaling. |

> [!NOTE]
> `p_core_only` and `e_core_only` conditions are automatically hardware-guarded. If executed on a non-heterogeneous CPU, the harness skips them with an explicit disclosure to prevent invalid benchmark claims.

---

## 2. Workload Synthesis

The workload generator spawns heterogeneous worker processes:
1. **Heavy Workers (`heavy_worker`):** Continuous compute-bound loop executing trial-division primality testing. Generates sustained CPU utilisation and involuntary context switches when competing for cores.
2. **Light Workers (`light_worker`):** I/O-bound loop performing rapid temporary disk file writes, flushes, and short sleep intervals. Characterized by high voluntary context switch frequencies and low CPU load.

Workloads support both **finite mode** (deterministic iteration count for automated benchmarking) and **infinite mode** (for continuous live dashboard streaming).

---

## 3. Evaluation Metrics

For each experimental condition across $N$ trials, the harness records:

1. **Mean CPU Utilization (%):** Average CPU core load across worker lifecycles.
2. **Voluntary Context Switch Rate:** Thread yields due to blocking I/O or sleep requests.
3. **Involuntary Context Switch Rate:** Preemptions by the OS scheduler due to time-slice expiration or core contention.
4. **Estimated Energy Proxy ($E_{\text{proxy}}$):** Modeled energy cost based on core residency:
   $$\text{Energy} = \sum_{t} \left( P_{\text{core\_weight}} \cdot \Delta t \right)$$
   where P-cores are assigned $1.0$ and E-cores are assigned $0.3$.
5. **Jain's Fairness Index:** Measures allocation equity across competing processes:
   $$\mathcal{J}(x_1, x_2, \dots, x_n) = \frac{\left( \sum_{i=1}^n x_i \right)^2}{n \sum_{i=1}^n x_i^2}$$
6. **Latency Percentiles (P95, P99):** Computed directly from the empirical distribution of per-cycle observations across all trials (never averaged across pre-aggregated percentiles).

---

## 4. Statistical Rigor Protocol

To substantiate research claims:

### Paired Two-Sided Welch's t-Test
Evaluates null hypothesis $H_0: \mu_{\text{bandit}} = \mu_{\text{baseline}}$:
$$t = \frac{\bar{X}_1 - \bar{X}_2}{\sqrt{\frac{s_1^2}{N_1} + \frac{s_2^2}{N_2}}}$$

### Cohen's $d$ Effect Size
Quantifies the standardized magnitude of performance difference:
$$d = \frac{\bar{X}_1 - \bar{X}_2}{s_{\text{pooled}}}, \quad s_{\text{pooled}} = \sqrt{\frac{s_1^2 + s_2^2}{2}}$$
- $|d| < 0.2$: Negligible
- $0.2 \le |d| < 0.5$: Small
- $0.5 \le |d| < 0.8$: Medium
- $|d| \ge 0.8$: Large effect

### Holm-Bonferroni Family-Wise Error Rate (FWER) Correction
Adjusts $p$-values across all pairwise baseline comparisons to control Type I false positive inflation:
$$p_{(k)} \le \frac{\alpha}{m - k + 1}$$

---

## 5. Execution Instructions

### Windows (PowerShell)
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Execute benchmark harness across all conditions (5 trials, 30 cycles each)
python -m aidax.evaluate --trials 5 --cycles 30 --output results/evaluation_results.json

# Generate statistical significance summary table
python -m aidax.analysis --input results/evaluation_results.json --format markdown
```

### Linux / macOS
```bash
source .venv/bin/activate
python -m aidax.evaluate --trials 5 --cycles 30 --output results/evaluation_results.json
python -m aidax.analysis --input results/evaluation_results.json --format markdown
```
