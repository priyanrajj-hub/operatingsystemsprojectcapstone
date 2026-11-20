# AI-DAX Deployment Guide

This guide covers deployment procedures for both the local hardware scheduling engine and the cloud-hosted Vercel dashboard.

---

## 1. Architecture Overview

AI-DAX separates scheduling telemetry and UI visualization:
1. **Host Scheduling Kernel (Local Machine):**
   - Python 3.10+ execution kernel (`src/aidax/` and `src/api/`).
   - Requires native hardware access (`psutil.cpu_affinity()`, MSR/RAPL).
   - Runs locally on loopback (`http://127.0.0.1:8000`).
2. **Web Dashboard & AI Edge Proxy (Vercel):**
   - Serves static assets (`static/index.html`, `static/app.js`, `static/style.css`).
   - Hosts serverless API proxy endpoints (`/api/aizen`, `/api/jarvis`) to safely bridge cloud LLM features.
   - Enforces strict Content Security Policy (CSP) and HTTP security headers.

---

## 2. Local Machine Deployment

### Step 1: Initialize Virtual Environment
**PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

**Bash:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Populate `.env` with your values. Note that `GEMINI_API_KEY` is optional; if omitted, AI-DAX operates in offline heuristic mode.

### Step 3: Launch Local Dashboard Backend
```powershell
python -m uvicorn aidax.api:app --host 127.0.0.1 --port 8000
```
Open your browser at `http://127.0.0.1:8000`.

---

## 3. Vercel Cloud Deployment

The Vercel deployment hosts the public dashboard and serverless LLM proxies.

### Step 1: Pre-Deployment Check
Ensure all local artifacts, secrets, and raw evaluation files are excluded:
```powershell
# Verify no secrets or sensitive files are tracked
git status
git check-ignore -v .env .env.local
```

### Step 2: Configure Vercel Environment Variables
**NEVER commit API keys to version control.** Set `GEMINI_API_KEY` directly within Vercel.

#### Option A: Via Vercel CLI
```powershell
# Authenticate
vercel login

# Link project
vercel link

# Add GEMINI_API_KEY (prompted securely for value)
vercel env add GEMINI_API_KEY
```
Select the target environments when prompted:
- `Production` (Required for live deployment)
- `Preview` (Required for PR previews)
- `Development` (Optional for local CLI dev)

#### Option B: Via Vercel Web Dashboard
1. Navigate to your project on [vercel.com](https://vercel.com).
2. Go to **Settings** > **Environment Variables**.
3. Add a new variable:
   - **Key:** `GEMINI_API_KEY`
   - **Value:** `<your-secret-api-key>`
   - **Environments:** Check `Production` and `Preview`.
4. Click **Save**.

### Step 3: Deploy to Vercel
```powershell
# Preview deployment
vercel

# Production deployment
vercel --prod
```

---

## 4. Post-Deployment Verification & Security Testing

Verify your deployment securely without echoing credentials:

1. **Verify Security Headers:**
   ```powershell
   curl -I https://your-project.vercel.app
   ```
   Confirm presence of:
   - `Content-Security-Policy`
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: camera=(), microphone=(self), geolocation=()`

2. **Verify Serverless Proxy Health:**
   Send a probe payload to test Aizen response format without exposing the underlying key:
   ```powershell
   curl -X POST https://your-project.vercel.app/api/aizen `
     -H "Content-Type: application/json" `
     -d '{"cpu_percent_overall": 45.0, "memory_percent": 60.0, "total_decisions": 100, "regret": 12.5}'
   ```
   Expected response: Structured JSON containing `health`, `process`, and `future` strings.

3. **Verify Zero Secret Leakage:**
   - Confirm that the response body contains NO raw key strings.
   - Inspect browser DevTools (Network tab) on `https://your-project.vercel.app`: verify that all requests to Gemini go through `/api/aizen` or `/api/jarvis` and that the request/response payloads contain zero bearer tokens.
