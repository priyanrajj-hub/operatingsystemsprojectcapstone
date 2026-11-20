# AI-DAX Lite — Developer & Contribution Guide

This guide describes development workflows, code quality standards, testing practices, and contribution procedures for AI-DAX Lite.

---

## 1. Project Directory Structure

```
operatingsystemsprojectcapstone/
├── api/                  # Modern FastAPI routes and schemas
├── config/               # Pydantic environment settings
├── docs/                 # Architectural specifications, audits & methodology
├── paper/                # IEEE research publication assets and LaTeX templates
├── results/              # Evaluation output files and benchmark figures
├── scripts/              # Automation and legacy migration scripts
├── src/
│   ├── aidax/            # Core AI-DAX package (scheduler, workload, API, eval)
│   ├── hardware/         # Multi-platform CPU topology detection
│   ├── persistence/      # SQLite async storage and atomic JSON checkpoints
│   ├── process/          # Safe PID tracking and affinity dispatchers
│   ├── scheduler/        # LinUCB bandit algorithms and online scalers
│   └── security/         # Secret masking, rate limiting, and token guards
├── static/               # Glassmorphic telemetry frontend (HTML5/CSS3/ES6)
├── tests/                # Comprehensive unit and integration test suite
└── pyproject.toml        # Ruff, mypy, pytest, and build configuration
```

---

## 2. Code Quality Standards

Every modification must adhere to strict formatting, linting, and typing checks prior to commit.

### Code Formatting
We enforce `ruff format` across the codebase:
```powershell
python -m ruff format src tests api scripts
```

### Static Analysis & Linting
Run `ruff check` with automatic rule enforcement:
```powershell
python -m ruff check src tests api scripts
```

### Strict Type Verification
Mypy validates strict static type annotations across all Python modules:
```powershell
python -m mypy src tests
```

### Test Suite Execution
Execute the full test suite with coverage reporting:
```powershell
python -m pytest
```

---

## 3. Git Workflow & Conventional Commits

We follow the Conventional Commits 1.0.0 specification:

- `feat:` Introduces a new feature or capability.
- `fix:` Patches a bug or defect.
- `refactor:` Restructures code without changing external behavior.
- `perf:` Optimizes runtime performance or algorithmic complexity.
- `test:` Adds or refactors unit/integration test cases.
- `docs:` Updates documentation, specifications, or diagrams.
- `chore:` Maintenance tasks, dependency updates, or configuration changes.

---

## 4. Pre-Commit Hooks

Install and configure pre-commit hooks to automate verification before each commit:

```bash
pip install pre-commit
pre-commit install
```
