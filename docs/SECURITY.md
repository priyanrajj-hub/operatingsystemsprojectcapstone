# AI-DAX Lite — Security Architecture & Threat Model

This document outlines the security controls, authentication mechanisms, and defenses implemented across the AI-DAX Lite platform.

For vulnerability disclosure procedures, please refer to [.github/SECURITY.md](file:///C:/Users/PRIYANRAJ%20J/.gemini/antigravity/scratch/operatingsystemsprojectcapstone/.github/SECURITY.md).

---

## 1. Threat Model & Key Attack Surfaces

| Threat Vector | Potential Impact | Implemented Mitigation |
|---|---|---|
| **Unauthenticated Network Exposure** | Remote control of process core affinities over local Wi-Fi / LAN | Telemetry server binds exclusively to `127.0.0.1` by default; CORS origins restricted. |
| **Confused Deputy Attack** | Attacker passing arbitrary system PIDs to starve or isolate critical processes | `/api/process/{pid}/affinity` strictly verifies target PID membership in `pids.txt`. |
| **PID-Reuse Race Condition** | Reused OS PID assigned affinity meant for terminated worker | Process registry validates `create_time` before dispatching affinity changes. |
| **Stored / DOM-based XSS** | Malicious process command lines or names executing script in dashboard | Frontend eliminates `innerHTML`; renders all telemetry via safe `textContent`. |
| **API Secret Leakage** | `GEMINI_API_KEY` or `AIDAX_API_TOKEN` committed to Git repository | Comprehensive `.gitignore`, `.secrets.baseline`, automated gitleaks pre-commit hooks, and in-memory secret masking. |
| **API Denial-of-Service** | Rapid unauthenticated requests exhausting AI rate limits or CPU cycles | In-memory sliding window rate limiters protect `/api/aizen` and `/api/jarvis`. |

---

## 2. Token-Based Authentication

Administrative actions that alter system state (starting/stopping the scheduler daemon, reassigning core affinities, triggering emergency resets) support token authentication:

```http
POST /api/process/1234/affinity
X-API-Token: <your-secure-token>
```

When `AIDAX_API_TOKEN` is defined in `.env`, any incoming request without a matching constant-time token comparison (`hmac.compare_digest`) is rejected with `401 Unauthorized`.

---

## 3. Secret Masking & Redaction

The configuration engine (`config/settings.py`) automatically masks all sensitive variables when serialized or printed in logs:
```python
repr(settings)  # Outputs: GEMINI_API_KEY=AIza****...
```
Raw secrets are never exposed to client-side browsers or logged to standard output.
