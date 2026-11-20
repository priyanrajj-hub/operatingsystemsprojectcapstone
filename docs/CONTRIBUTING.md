# Contributing to AI-DAX Lite

Thank you for contributing to AI-DAX Lite. This document outlines guidelines for code quality, testing, environment setup, and submission procedures.

---

## 1. Development Setup

### Python Version
Python 3.10 or higher is required (tested on Python 3.10, 3.11, 3.12, 3.13).

### Environment Creation

#### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

#### Linux / macOS (Bash)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

---

## 2. Code Quality & Pre-commit Standards

We enforce strict linting, formatting, and type-checking standards:

### Static Analysis & Formatting
- **Linter:** [Ruff](https://github.com/astral-sh/ruff)
- **Rules:** `E`, `F`, `W`, `I`, `B`, `C4`, `UP`
- **Line Length:** 100 characters

```powershell
# Format code
python -m ruff format src tests api scripts

# Check for lint errors
python -m ruff check src tests api scripts
```

### Static Type Checking
- **Type Checker:** [Mypy](https://mypy-lang.org/)
- All new public functions and methods must have full type annotations.

```powershell
python -m mypy src tests
```

---

## 3. Testing Requirements

All contributions must follow test-driven practices:

1. **Unit Tests:** Placed in `tests/` with prefix `test_*.py`.
2. **Execution:**
   ```powershell
   python -m pytest
   ```
3. **Coverage:** Core algorithmic modules in `src/aidax/` must maintain at least 50% line coverage with zero test failures or unhandled warnings.
4. **Deterministic Math:** Bandit updates must maintain mathematical stability (Sherman-Morrison rank-1 formula, Welford running variance, finite context values).

---

## 4. Git Workflow & Conventional Commits

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` New features
- `fix:` Bug fixes
- `refactor:` Code reorganization without functional changes
- `test:` Adding or updating tests
- `docs:` Documentation improvements
- `chore:` Dependency bumps, tooling, or build configuration

### Branch Naming Conventions
- `feat/feature-name`
- `fix/bug-description`
- `chore/task-name`

---

## 5. Security & Sensitive Data Policy

- **Zero Secrets:** Never commit `.env` files, API keys, tokens, or credentials.
- **Masking:** Secrets in error logs or representations must be masked (e.g., `AIza****`).
- **Input Validation:** User-provided metrics or network parameters must be validated with Pydantic schemas before processing.
