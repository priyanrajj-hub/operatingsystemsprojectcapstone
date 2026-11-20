# AI-DAX Lite Evaluation Methodology & Mathematical Formulation

## Contextual Bandit Mathematical Formulation

Traditional heuristic operating system schedulers use static thresholding or offline-trained classifiers on synthetic labels. AI-DAX replaces synthetic proxy training with an online **LinUCB contextual multi-armed bandit** that learns directly from measured operating system outcome deltas.

### LinUCB Parameter Updates

Each arm $a \in \{0, 1\}$ maintains:
- A $d \times d$ regularized design matrix $\mathbf{A}_a$, initialized as $\mathbf{I}_d$.
- A $d$-dimensional reward accumulator vector $\mathbf{b}_a$, initialized as $\mathbf{0}_d$.
- An estimated ridge regression weight vector $\boldsymbol{\theta}_a = \mathbf{A}_a^{-1} \mathbf{b}_a$.

Given an observed feature context $\mathbf{x}_t \in \mathbb{R}^d$, the upper confidence bound (UCB) score for arm $a$ is computed as:

$$\text{UCB}_a(\mathbf{x}_t) = \mathbf{x}_t^T \boldsymbol{\theta}_a + \alpha_{\text{explore}} \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t}$$

The action selected at cycle $t$ is:

$$a_t = \arg\max_{a} \text{UCB}_a(\mathbf{x}_t)$$

Upon observing the real outcome reward $r_{t, a_t}$, arm parameters are updated incrementally:

$$\mathbf{A}_{a_t} \leftarrow \mathbf{A}_{a_t} + \mathbf{x}_t \mathbf{x}_t^T$$

$$\mathbf{b}_{a_t} \leftarrow \mathbf{b}_{a_t} + r_{t, a_t} \mathbf{x}_t$$

---

## Reward Formulation

The multi-objective reward function balances CPU contention (involuntary context switches) against simulated core power consumption:

$$R_t = -\left(\alpha \cdot \min\left(\frac{\text{InvolCtxRate}}{1000}, 1.0\right) + \beta \cdot E_{\text{proxy}}\right)$$

Default hyperparameters:
- $\alpha = 0.7$ (penalty weight for involuntary context switches)
- $\beta = 0.3$ (penalty weight for energy proxy)
- $E_{\text{proxy}} = 1.0$ for Performance cores ($a=0$), $0.3$ for Efficiency cores ($a=1$). On Intel hybrid architectures (e.g., Alder Lake/Raptor Lake), P-cores draw approximately $3\times$ to $4\times$ the power of E-cores during peak computation.

---

## Evaluation Experimental Setup

The evaluation harness executes the identical workload under four experimental conditions across multiple trials:

1. **`baseline_cfs`**: Standard OS Completely Fair Scheduler baseline with no user-space CPU affinity constraints.
2. **`static_naive`**: Fixed heuristic routing without adaptation: all compute-heavy processes are permanently bound to P-cores, and all I/O-light processes to E-cores.
3. **`heuristic_only`**: Dynamic threshold-based reclassification without contextual learning: processes are re-evaluated each cycle based on static thresholds.
4. **`bandit_adaptive`**: Full AI-DAX LinUCB contextual bandit algorithm with online feature scaling, exploration bonus, and measured feedback updates.

### Evaluated Metrics

- **Mean CPU Utilization (%)**: Average processor utilization of active workload tasks.
- **Involuntary Context Switches**: Frequency of preemption events caused by time-slice expiration or core starvation.
- **Jain's Fairness Index ($J$)**:
  $$J = \frac{\left(\sum_{i=1}^n x_i\right)^2}{n \cdot \sum_{i=1}^n x_i^2}$$
  where $x_i$ is the total CPU execution time allocated to process $i$.
- **Heavy Task Completion Time ($s$)**: Elapsed wall-clock time required for CPU-bound tasks to complete finite prime calculations.

### Statistical Validation

Paired two-tailed Student's t-tests (`scipy.stats.ttest_rel`) evaluate whether differences between `bandit_adaptive` and each baseline condition achieve statistical significance at the $\alpha = 0.05$ threshold.
