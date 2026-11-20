# AI-DAX Lite — Research Methodology & Mathematical Formulation

## 1. Problem Formulation: Contextual Multi-Armed Bandit

Operating system CPU scheduling on asymmetric heterogeneous multicore processors presents a fundamental exploration-exploitation trade-off. At runtime, the operating system kernel must assign threads to cores with differing performance, microarchitecture, and power characteristics without prior knowledge of thread execution phases.

AI-DAX Lite formalizes thread-to-core affinity routing as a **contextual multi-armed bandit (MAB)** problem.

### Action Space $\mathcal{A}$
In a heterogeneous dual-cluster topology (Performance cores and Efficiency cores), the action set consists of two discrete arms:
$$\mathcal{A} = \{0, 1\}$$
- $a=0$: Performance Core Cluster (P-cores)
- $a=1$: Efficiency Core Cluster (E-cores)

### Context Feature Vector $\mathbf{x}_t \in \mathbb{R}^d$
At each scheduling epoch $t$, for each monitored process $p$, the context vector $\mathbf{x}_t \in \mathbb{R}^4$ captures dynamic execution telemetry:
$$\mathbf{x}_t = \begin{bmatrix} \tilde{u}_t \\ \tilde{v}_t \\ \tilde{w}_t \\ 1.0 \end{bmatrix}$$
where:
1. $\tilde{u}_t$: Normalized CPU utilization percentage of the process.
2. $\tilde{v}_t$: Normalized voluntary context switch rate (representing I/O blocking and yielding).
3. $\tilde{w}_t$: Normalized involuntary context switch rate (representing CPU preemption and thread contention).
4. $1.0$: Constant bias term.

---

## 2. Online Feature Scaling via Welford's Algorithm

To prevent feature magnitude disparity from biasing $L_2$-regularized regression, incoming raw telemetry is normalized online using Welford's one-pass algorithm for running mean and sample variance:

$$\bar{x}_k = \bar{x}_{k-1} + \frac{x_k - \bar{x}_{k-1}}{k}$$

$$M_{2, k} = M_{2, k-1} + (x_k - \bar{x}_{k-1})(x_k - \bar{x}_k)$$

$$\sigma_k^2 = \frac{M_{2, k}}{k - 1} \quad (k \ge 2)$$

Standardized context features are computed as:
$$\tilde{x}_k = \frac{x_k - \bar{x}_k}{\sqrt{\sigma_k^2 + \epsilon}}$$
with cold-start threshold $k < 10$ using initial empirical scaling.

---

## 3. LinUCB with Sherman-Morrison Numerical Optimization

Each arm $a \in \mathcal{A}$ maintains:
- Design matrix $\mathbf{A}_a \in \mathbb{R}^{d \times d}$, initialized to identity $\mathbf{I}_d$.
- Response vector $\mathbf{b}_a \in \mathbb{R}^d$, initialized to $\mathbf{0}_d$.
- Inverse design matrix $\mathbf{A}_a^{-1}$, initialized to $\mathbf{I}_d$.

### Upper Confidence Bound (UCB) Score
For an observed context $\mathbf{x}_t$:
$$\text{UCB}_a(\mathbf{x}_t) = \mathbf{x}_t^T \boldsymbol{\theta}_a + \alpha_{\text{explore}} \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t}$$
where $\boldsymbol{\theta}_a = \mathbf{A}_a^{-1} \mathbf{b}_a$ is the ridge regression coefficient vector, and $\alpha_{\text{explore}} \in \mathbb{R}^+$ controls the exploration bonus width.

### Sherman-Morrison $O(d^2)$ Rank-1 Update
Direct inversion of $\mathbf{A}_a$ at each step requires $O(d^3)$ computation. AI-DAX Lite employs the Sherman-Morrison formula to update the inverse matrix in $O(d^2)$ time:

$$\mathbf{A}_{\text{new}}^{-1} = \left(\mathbf{A} + \mathbf{x}_t \mathbf{x}_t^T\right)^{-1} = \mathbf{A}^{-1} - \frac{\mathbf{A}^{-1} \mathbf{x}_t \mathbf{x}_t^T \mathbf{A}^{-1}}{1 + \mathbf{x}_t^T \mathbf{A}^{-1} \mathbf{x}_t}$$

$$\mathbf{b}_a \leftarrow \mathbf{b}_a + r_t \mathbf{x}_t$$

This reduces per-decision scheduling overhead to sub-millisecond execution.

---

## 4. Multi-Objective Reward Function

The reward function reflects systems engineering goals: penalizing core contention while optimizing energy efficiency.

$$r_t = -\left( \alpha \cdot \min\left(\frac{\text{InvolCtxRate}_t}{1000}, 1.0\right) + \beta \cdot E_{\text{proxy}}(a_t) \right)$$

where:
- $\alpha = 0.7$: Weight on reducing involuntary context switch preemption.
- $\beta = 0.3$: Weight on energy conservation.
- $E_{\text{proxy}}(a_t) \in \{1.0, 0.3\}$: Estimated power draw proxy ($1.0$ for P-cores, $0.3$ for E-cores).

---

## 5. Regret Analysis & Methodological Disclosures

### Pseudo-Regret Formulation
Because the true counterfactual reward $r_{t, a^*}$ for the unchosen arm is unobservable in physical systems without simultaneous execution, cumulative regret is computed relative to an empirical oracle baseline:

$$\mathcal{R}_T = \sum_{t=1}^T \left( r_t^* - r_t \right)$$

### Methodological Boundaries
1. **User-Space vs Kernel Scheduler:** AI-DAX Lite operates via user-space CPU affinity masks (`sched_setaffinity` / `SetProcessAffinityMask`). It influences the kernel scheduler's candidate core set rather than overriding kernel dispatch queues directly.
2. **Simulated Energy Proxy:** Modeled energy consumption ($E_{\text{proxy}}$) is a microarchitectural proxy. Production deployment requires hardware counter readings (Intel RAPL, AMD Energy Driver, or Apple SMC).
3. **Hardware Fallback Disclosure:** On homogeneous architectures or unsupported operating systems (such as macOS Darwin Mach), the system documents fallback to logical affinity partitioning.
