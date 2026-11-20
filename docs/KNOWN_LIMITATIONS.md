# AI-DAX Lite — Known Limitations & Research Disclosures

This document details the architectural boundaries, hardware dependencies, and methodological limitations of AI-DAX Lite (*Adaptive Intelligence for Dynamic Allocation and Execution*).

---

## 1. User-Space CPU Affinity Management vs. Kernel Scheduling

### Architectural Boundary
AI-DAX Lite is a **user-space CPU affinity management and policy supervision platform**. It does **not** replace the operating system's internal kernel scheduler (such as Linux CFS / EEVDF or the Windows NT thread dispatcher).

### Mechanics
- The system modulates process affinity masks via standard platform system calls:
  - **Linux:** `sched_setaffinity(2)` via `psutil.Process.cpu_affinity()`.
  - **Windows:** `SetProcessAffinityMask` via Win32 API / `psutil`.
- The native OS kernel remains responsible for fine-grained millisecond quantum allocation, interrupt handling, sleep/wake states, and thread preemption within the allocated core masks.

---

## 2. Hardware Topology & Platform Heterogeneity

### True Heterogeneous Hardware Requirements
- Direct hardware-level Performance Core (P-core) and Efficient Core (E-core) allocation requires hardware that implements hybrid microarchitectures:
  - **Intel:** 12th Generation Alder Lake, 13th Gen Raptor Lake, 14th Gen, or Core Ultra (Meteor Lake / Arrow Lake) with Intel Thread Director support.
  - **ARM:** big.LITTLE or DynamIQ systems (e.g. Apple Silicon, Raspberry Pi 5 with heterogeneous clusters, or modern Snapdragon/Dimensity SoCs).

### Homogeneous Hardware Behavior (`SIMULATED PARTITION`)
- On systems with symmetric homogeneous cores (e.g., standard AMD Ryzen processors, Intel Core pre-12th generation, cloud virtual machines, or continuous integration runners):
  - AI-DAX identifies the absence of hardware hybrid core attributes.
  - The system partitions the available logical cores into two equal or configured pools (e.g., lower half assigned to simulated P-cores, upper half assigned to simulated E-cores).
  - The scheduler logs an explicit warning: `Operating with SIMULATED PARTITION on non-hybrid host`.
  - Experimental evaluations run identically to validate algorithmic convergence and load routing, but physical power or IPC divergence reflects synthetic partitioning rather than distinct silicon microarchitectures.

---

## 3. macOS Platform Constraints

- **Mach Kernel Limitation:** macOS does not support thread-level or process-level hard CPU affinity binding. The `psutil.Process.cpu_affinity()` method raises `AttributeError` on Darwin kernels.
- **AI-DAX Handling:** The system automatically detects Darwin, bypasses affinity manipulation, logs a notification, and functions strictly in metric observation and simulator mode.

---

## 4. Partial Observability & Regret Calculation

### The Bandit Feedback Constraint
In online contextual bandit optimization, the agent observes feedback *only* for the chosen arm $a_t \in \mathcal{A}$:
$$r_t = r(a_t, x_t)$$
The rewards for unchosen counterfactual actions ($a \neq a_t$) are fundamentally unobservable in a live single-execution operating system environment.

### Mathematical Regret Distinction
1. **True Theoretical Regret:** Requires knowing the optimal arm reward $r(a_t^*, x_t)$, which cannot be measured simultaneously on a single physical host without time-travel or identical workload replay:
   $$R_T = \sum_{t=1}^T \left( r(a_t^*, x_t) - r(a_t, x_t) \right)$$
2. **Estimated Operational Regret:** In live deployment, regret is computed relative to an empirically estimated baseline policy (e.g. static heuristic reward expectations) or within our controlled multi-trial ground-truth simulator.
3. **Disclosure:** Reported cumulative regret curves in live telemetry reflect estimated policy delta, not counterfactual omniscient regret.

---

## 5. Energy Consumption Estimation Proxy

- **Physical RAPL Limitations:** Access to Intel RAPL (Running Average Power Limit) or AMD energy sensors under Linux requires root privileges (`CAP_SYS_RAWIO` or read access to `/sys/class/powercap/intel-rapl/`). On Windows, direct hardware energy sampling requires specialized kernel drivers (e.g. Intel Power Gadget / PCM).
- **AI-DAX Proxy Method:** In unprivileged installations, power consumption is reported as an **Estimated Energy Proxy** computed from per-core active frequency, utilization percentage, and nominal thermal design power (TDP) coefficients:
  $$\hat{P}(t) = P_{\text{idle}} + \sum_{i \in \text{P-cores}} \alpha_P \cdot u_i(t) \cdot f_i(t) + \sum_{j \in \text{E-cores}} \alpha_E \cdot u_j(t) \cdot f_j(t)$$
- Energy metrics must not be interpreted as physical calorimeter or hardware wattmeter readings unless RAPL sensors are explicitly available and configured.

---

## 6. Containerization & Virtualization Boundaries

- **Docker & Podman:** Standard unprivileged container execution isolates Linux namespaces (`pid`, `cgroup`, `ipc`). A containerized process manager cannot modify the CPU affinity of host processes outside its container namespace.
- **Deployment Requirement:** For AI-DAX to manage host processes from within a container, the container must be executed with host namespace sharing (`--pid=host`) and administrative scheduling privileges (`--cap-add=SYS_NICE`).
- **Kubernetes:** Manifests provided in `k8s/` are intended for dashboard/telemetry demonstration and simulator evaluation; standard multi-tenant Kubernetes pods should not be granted host affinity control.
