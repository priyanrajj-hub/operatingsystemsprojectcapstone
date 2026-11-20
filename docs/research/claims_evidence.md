# Claims-Evidence Traceability Matrix

Every empirical, algorithmic, or security claim asserted in the research paper must map directly to an entry in this traceability matrix. Claims without verified raw data and code reproduction scripts are rejected.

| Claim ID | Paper Claim Statement | Target Figure / Table | Raw Data Source File | Generating Script / Test | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | LinUCB achieves sublinear cumulative regret $\mathcal{O}(\sqrt{T \ln T})$ in ground-truth simulation. | Figure 3 (Regret vs Time) | `data/processed/sim_regret.json` | `src/experiments/simulator.py` | Verified (Simulation) |
| **C2** | Frozen Welford scaling maintains stationary feature coordinates, avoiding moving-coordinate divergence. | Section IV-B & Table 2 | `tests/test_bandit.py` | `src/scheduler/linucb.py` | Verified (Unit Tests) |
| **C3** | Contextual Thompson Sampling provides comparable regret to LinUCB under stationary payoff distributions. | Figure 3 | `data/processed/sim_regret.json` | `src/experiments/simulator.py` | Verified (Simulation) |
| **C4** | Process creation timestamp checks eliminate PID reuse race conditions across process recycling events. | Section V-A | `tests/test_scheduler.py` | `src/process/registry.py` | Verified (Automated Test) |
| **C5** | Cryptographic SHA-256 envelopes reject tampered model weights prior to deserialization. | Section V-C | `tests/test_persistence.py` | `src/persistence/checkpoints.py` | Verified (Automated Test) |
| **C6** | Adversarial context-switch inflation causes policy misallocation unless mitigated by rate limiting and robust scaling. | Figure 5 (Adversarial Degradation) | `data/processed/adversarial_results.json` | `src/security/adversarial.py` | Verified (Pilot Benchmark) |
| **C7** | User-space scheduler introduces $< 2.5\%$ CPU overhead and sub-millisecond per-decision latency at $N=16$. | Table 4 (Overhead Scaling) | `data/processed/overhead_bench.json` | `scripts/bench_overhead.py` | Verified (Empirical Run) |
| **C8** | Hardware topology detection on non-Linux systems honestly reports simulated partition mode with zero false hardware claims. | Section III-A & env.json | `env.json` | `scripts/platform_check.py` | Verified (Platform Check) |
