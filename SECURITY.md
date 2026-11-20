# Security Policy: AI-DAX

The AI-DAX engineering team takes the security of our heterogeneous CPU scheduling simulator and its telemetry components seriously. We appreciate responsible disclosure of vulnerabilities.

---

## Supported Versions

Only the latest release and the current active development branch receive security patches and updates.

| Version | Supported | Notes |
| :--- | :--- | :--- |
| `1.x` (current main) | :white_check_mark: | Active support and maintenance |
| `< 1.0.0` (legacy prototype) | :x: | Deprecated; upgrade recommended |

---

## Reporting a Vulnerability

**DO NOT report security vulnerabilities via public GitHub issues, discussions, or pull requests.**

If you discover a security vulnerability or credential exposure:
1. **GitHub Security Advisory (Preferred):** Open a private advisory report under the repository's **Security** tab > **Report a vulnerability**.
2. **Email Disclosure:** Contact the repository maintainer directly at: `priyanrajj@gmail.com` with the subject line `[SECURITY] AI-DAX Vulnerability Report`.

Please include the following information in your report:
- Type of issue (e.g., secret leakage, unauthorized affinity modification, injection, XSS).
- Affected files, functions, or endpoints.
- Step-by-step reproduction instructions or proof-of-concept script.
- Potential impact and your assessment of severity.

---

## Response Timeline Commitments

We adhere to coordinated vulnerability disclosure timelines:
- **Initial Acknowledgement:** Within **48 hours** of report receipt.
- **Triage & Severity Assessment:** Within **5 business days**.
- **Fix & Advisory Release:** Critical vulnerabilities are patched within **14 business days**.
- **Public Disclosure:** Coordinated after fixes are deployed and verified.

---

## Scope

### In-Scope Vulnerabilities
- Credential and secret exposure (API keys, OAuth tokens, session secrets).
- Cross-Site Scripting (XSS) in the dashboard interface.
- Remote or cross-origin process affinity manipulation (unauthorized core reassignment).
- Server-side request forgery (SSRF) or injection in backend AI proxies (`/api/aizen`, `/api/jarvis`).
- Bypass of PID ownership validation and confused-deputy process attacks.
- Checkpoint tampering or deserialization vulnerabilities.

### Out-of-Scope
- Denial of Service (DoS) attacks requiring high-rate flooding against local loopback interfaces (`127.0.0.1`).
- Attacks requiring existing root/administrator access or malware already operating on the host machine.
- Social engineering or physical access attacks against developer hardware.
- Third-party infrastructure outages (Google AI Studio, Vercel edge networks).
