# AI-DAX Lite — Installation & Setup Guide

This guide details environment setup, dependency installation, and verification steps across Windows, Linux, macOS, and containerized Docker environments.

---

## 1. Prerequisites
- **Python:** Version 3.10, 3.11, 3.12, or 3.13.
- **Git:** 2.30+
- **Privileges:** Standard user privileges (administrative / root rights are **not** required for user-space affinity management).

---

## 2. Windows 11 (PowerShell) Setup

### Clone Repository
```powershell
git clone https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone.git
cd operatingsystemsprojectcapstone
```

### Create & Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> [!NOTE]
> If script execution is restricted by PowerShell policy, run:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Configure Environment Variables
```powershell
Copy-Item .env.example .env
```
*(Optionally populate `GEMINI_API_KEY` or `AIDAX_API_TOKEN` inside `.env`)*

### Verify Installation
```powershell
python -m pytest
```

---

## 3. Linux (Ubuntu / Debian) Setup

```bash
# Clone
git clone https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone.git
cd operatingsystemsprojectcapstone

# Create Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# Install Dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure Environment
cp .env.example .env

# Run Test Suite
pytest
```

---

## 4. macOS Setup & Limitations

```bash
git clone https://github.com/priyanrajj-hub/operatingsystemsprojectcapstone.git
cd operatingsystemsprojectcapstone
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

> [!WARNING]
> **macOS Platform Boundary:**  
> The macOS Darwin Mach kernel does not expose user-space thread affinity interfaces (`psutil.Process.cpu_affinity()` raises `AttributeError`).  
> AI-DAX automatically detects Darwin and activates graceful degradation mode, reporting `is_heterogeneous = false` and logging affinity operations as simulated passes.

---

## 5. Docker & Docker Compose Setup

Run the full system in an isolated container:

```bash
# Build and launch telemetry hub on port 8000
docker-compose up --build
```

Access the dashboard at `http://localhost:8000`.

---

## 6. Running the Application

### 1. Launch FastAPI Telemetry Hub
```powershell
# PowerShell
python -m aidax.api
```

### 2. Launch Workload Generator & Scheduler (Separate Terminal)
```powershell
# In another terminal window:
python -m aidax.workload --infinite
python -m aidax.scheduler
```

Open your browser to:
```
http://127.0.0.1:8000
```
