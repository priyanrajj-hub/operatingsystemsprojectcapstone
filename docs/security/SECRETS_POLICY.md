# Secrets Management & Key Rotation Policy

This document defines the secrets management standard, developer workflow, and emergency rotation runbooks for the AI-DAX project.

---

## 1. Core Principles

1. **Zero Secret Check-ins:** Secrets, tokens, connection strings, and private keys must **NEVER** be committed to Git.
2. **Server-Side Isolation:** The browser frontend (`static/`) must **NEVER** hold or process raw third-party credentials. All external AI queries must route through backend proxy endpoints.
3. **Defense in Depth:** All configuration loads via `core.config.settings`, which scrubs and masks credentials in string representations (`repr()`, logs, console dumps).
4. **Pre-Commit Enforcement:** Local Git commits must pass automated `gitleaks` and `detect-secrets` checks configured in `.pre-commit-config.yaml`.

---

## 2. Developer Workflow

### Storing Local Secrets
- Copy `.env.example` to `.env`:
  ```bash
  cp .env.example .env
  ```
- `.env` and `.env.local` are explicitly listed in `.gitignore` and must remain untracked.
- Never hardcode API keys or secrets in source files or scripts. Always load via `from core.config import settings`.

### Verification Before Commit
Before pushing code, run the local secret audit:
```bash
python scripts/safe_secret_scanner.py
git status --ignored
```
Ensure that no `.env` or untracked credential artifacts are staged.

---

## 3. Key Rotation Runbooks

If any credential is compromised or suspected of exposure, follow these step-by-step rotation runbooks immediately.

### Runbook A: Google / Gemini API Key
1. **Revoke Existing Key:**
   - Log in to [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Locate the active key in the **API Keys** management dashboard.
   - Click the delete/trash icon to immediately invalidate the compromised key.
2. **Provision New Key:**
   - Click **Create API Key**.
   - Select the target Google Cloud project.
   - Copy the new key (format: `AIzaSy...` or `AQ....`).
3. **Update Local Environment:**
   - In `.env`, update: `GEMINI_API_KEY=<new_key_value>`.
4. **Update Cloud Deployment (Vercel):**
   ```bash
   vercel env rm GEMINI_API_KEY production
   vercel env add GEMINI_API_KEY production
   ```
   Or update via **Project Settings** > **Environment Variables** on the Vercel dashboard.
5. **Verify:**
   - Run local health check: `python -m pytest tests/test_security_env.py`.

---

### Runbook B: Vercel OIDC & Deployment Tokens
1. **Revoke Existing Tokens:**
   - Go to [Vercel Account Settings > Tokens](https://vercel.com/account/tokens).
   - Find the token used for CLI or CI/CD deployment and click **Revoke**.
2. **Clean Local Workspaces:**
   - Delete cached tokens:
     ```bash
     rm -rf .vercel static/.vercel .env.local static/.env.local
     ```
3. **Re-authenticate:**
   - Run `vercel login` to generate a fresh, short-lived session token.

---

### Runbook C: GitHub Personal Access Tokens
1. Go to [GitHub Settings > Personal Access Tokens](https://github.com/settings/tokens).
2. Locate the token, click **Revoke**, and confirm.
3. Generate a replacement fine-grained token with minimum necessary repository permissions.
4. Update GitHub Actions repository secrets if used in CI.

---

## 4. Emergency Incident Response: Accidental Git Commit

If a secret is accidentally committed to Git:

1. **Step 1: Immediate Invalidation (T=0)**
   - **Immediately revoke and rotate the secret** at the service provider (Runbook A/B/C).
   - Do NOT assume deleting the commit in Git removes the risk; automated scrapers index public GitHub commits in under 60 seconds.
2. **Step 2: Quarantine the Branch**
   - Alert the engineering team.
3. **Step 3: History Rewriting Protocol (`git-filter-repo`)**
   - After user confirmation and key revocation:
     ```bash
     pip install git-filter-repo
     git filter-repo --replace-text <(echo "compromised_secret_value==>REDACTED_SECRET")
     ```
   - Force-push requires explicit maintainer review and approval.
