# AI-DAX Research Preregistration Plan

## 1. Study Overview
- **Title:** An Empirical Evaluation of Contextual Bandit-Based Adaptive CPU Affinity Management on Heterogeneous Multicore Processors
- **Principal Investigator:** Priyanraj J.
- **Repository:** `https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone`
- **Branch:** `research/paper-artifact`
- **Preregistration Timestamp:** 2026-11-20
- **Status:** **FROZEN PRIOR TO FINAL BENCHMARK EXECUTION**

---

## 2. Research Questions (RQs)

- **RQ1 (Kernel Scheduler Comparison):** Does adaptive user-space LinUCB affinity placement improve held-out application performance metrics (throughput and tail latency) compared to the default unconstrained OS scheduler (CFS)?
- **RQ2 (Comparative Policy Efficiency):** How does LinUCB compare against static pinning (all-P, all-E), simple heuristic rules, random allocation, $\epsilon$-greedy linear, Bayesian Linear Thompson Sampling (LinTS), and an offline oracle static reference?
- **RQ3 (Regret & Convergence Dynamics):** What is the cumulative regret and parameter convergence rate of LinUCB in ground-truth simulation and empirical execution?
- **RQ4 (Energy-Performance Pareto Trade-Off):** How does adaptive routing affect system-level power consumption and Energy-Delay Product (EDP) when measured via hardware RAPL or power proxies?
- **RQ5 (Adversarial Robustness & Mitigations):** How vulnerable is LinUCB to feature-manipulation attacks (context-switch inflation, CPU spoofing, feature mimicry), and do robust scaling and rate-limiting mitigations successfully prevent victim degradation?
- **RQ6 (System Overhead):** What CPU utilization, memory footprint, and decision latency does the user-space scheduling daemon impose as the managed process count scales?

---

## 3. Evaluated Conditions

All conditions execute identical workloads under uniform thermal and frequency conditions:
1. `cfs`: Unconstrained OS Completely Fair Scheduler (Arm 2, all cores enabled).
2. `static_p`: Fixed pinning to Performance cores only (Arm 1).
3. `static_e`: Fixed pinning to Efficient cores only (Arm 0).
4. `static_heuristic`: CPU-utilization threshold rule (> 50% $\to$ P-core, < 20% $\to$ E-core, else unpinned).
5. `random`: Uniform stochastic arm selection among {0, 1, 2}.
6. `round_robin`: Deterministic cyclic alternation between E-core, P-core, and unpinned.
7. `epsilon_greedy`: Linear exploration with $\epsilon = 0.10$.
8. `thompson_sampling`: Bayesian Linear Thompson Sampling with parameter posterior sampling ($v = 0.3$).
9. `linucb`: Contextual Linear Upper Confidence Bound policy with Cholesky solve and ridge regularization ($\alpha = 1.0, \lambda = 1.0$).
10. `oracle_static`: Hindsight offline optimal static core assignment per workload category.

---

## 4. Evaluated Workload Kernels

Versioned and deterministic kernels initialized with explicit seeds:
1. **CPU-Intensive:** Continuous dense matrix multiplications ($150 \times 150$).
2. **Memory-Intensive:** Strided array traversals (32\,MB buffer) inducing L3/LLC cache misses.
3. **Bursty Compute:** Alternating 200\,ms high-intensity spin with 300\,ms sleep slices.
4. **I/O-Intensive:** Synchronous disk writes with `os.fsync` flushes.
5. **Phase-Changing Non-Stationary:** Workload dynamically switching from compute-heavy to memory-heavy mid-run to test bandit adaptivity.
6. **Scaling Workload:** Multi-process concurrency sweep across $N \in \{2, 4, 8, 16\}$ active processes.

---

## 5. Metrics Formulation

### 5.1 Primary Metrics (Held-Out from Reward)
- **Application Throughput:** Completed task units or iterations per elapsed second ($W / \Delta t$).
- **Makespan:** Total completion wall-clock time for batch tasks.
- **Latency Distribution:** Mean, 95th percentile (P95), and 99th percentile (P99) cycle latency.
- **Relative Slowdown:** Execution time normalized against that PID's own unpinned CFS baseline.

### 5.2 Secondary Metrics
- **Involuntary Context Switches:** Cumulative OS context switches (`psutil.num_ctx_switches().involuntary`).
- **Jain's Fairness Index:** $J(x_1, \dots, x_n) = \frac{(\sum x_i)^2}{n \sum x_i^2} \in [0, 1]$ across active processes.
- **Package Energy & EDP:** Measured Intel RAPL energy ($\Delta E$ in Joules) and Energy-Delay Product ($\text{EDP} = P_{\text{avg}} \cdot T^2$).
- **Scheduler Overhead:** CPU% consumption and decision latency ($\mu\text{s}$) of the Python daemon.

---

## 6. Experimental Protocol

- **Pilot Phase:** 10 trials per condition to estimate variance, test execution stability, and verify statistical power.
- **Final Test Phase:** $\ge 30$ independent runs per condition per workload.
- **Randomization:** Condition execution order is randomized using block permutations to counter thermal throttling drift.
- **Warm-Up & Cool-Down:** Discard initial 5-second warm-up; enforce 5-second cool-down idle period between runs.
- **Hyperparameter Freezing:** All tuning (e.g., $\alpha, \lambda$) is conducted exclusively on separate tuning seeds, committed to `config/frozen_hyperparams.yaml`, and never altered during test runs.

---

## 7. Statistical Analysis Pipeline

- **Descriptive Statistics:** Mean, Standard Deviation, Median, Interquartile Range (IQR).
- **Confidence Intervals:** 95% non-parametric bootstrap confidence intervals (10,000 resamples).
- **Normality Testing:** Shapiro-Wilk test on sample residuals.
- **Omnibus Hypothesis Test:** Friedman test across all scheduling conditions.
- **Post-Hoc Pairwise Testing:** Pairwise Wilcoxon signed-rank tests comparing LinUCB against each baseline, adjusted for multiple comparisons via the Holm-Bonferroni step-down correction.
- **Effect Sizes:** Cohen's $d$ and non-parametric Cliff's $\delta$.
