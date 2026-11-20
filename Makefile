.PHONY: venv install run eval test lint format clean help platform-check pilot tune final analyze figures reproduce-sim reproduce

VENV ?= .venv
PYTHON = $(VENV)/bin/python
ifeq ($(OS),Windows_NT)
    PYTHON = $(VENV)/Scripts/python.exe
endif

help:
	@echo "Available make targets:"
	@echo "  platform-check - Verify hardware platform truth and hybrid core detection"
	@echo "  pilot          - Run pilot evaluation across core scheduling policies"
	@echo "  reproduce-sim  - Execute simulator and adversarial robustness benchmarks"
	@echo "  reproduce      - Complete reproduction pipeline on native hybrid hardware"
	@echo "  figures        - Generate publication-quality vector PDFs and LaTeX macros"
	@echo "  test           - Run pytest suite with coverage"
	@echo "  lint           - Run ruff linter and mypy type checks"
	@echo "  format         - Run ruff code formatter"
	@echo "  clean          - Remove build artifacts, pycache, and temporary state"

venv:
	python3 -m venv $(VENV) || python -m venv $(VENV)

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,llm]"

platform-check:
	$(PYTHON) scripts/platform_check.py --allow-simulated

pilot:
	$(PYTHON) scripts/run_pilot_bench.py

tune:
	$(PYTHON) -m aidax.evaluate --duration 10 --trials 2

final:
	$(PYTHON) -m aidax.evaluate --duration 30 --trials 10

analyze:
	$(PYTHON) -m aidax.analysis

figures:
	$(PYTHON) scripts/generate_figures.py

reproduce-sim:
	$(PYTHON) scripts/run_simulator_bench.py
	$(PYTHON) scripts/run_adversarial_bench.py
	$(PYTHON) scripts/bench_overhead.py
	$(PYTHON) scripts/generate_figures.py

reproduce: platform-check pilot reproduce-sim

run:
	$(PYTHON) -m uvicorn api.app:app --host 127.0.0.1 --port 8000

eval:
	$(PYTHON) -m aidax.evaluate --duration 60 --trials 5

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests scripts
	$(PYTHON) -m mypy src

format:
	$(PYTHON) -m ruff format src tests scripts

clean:
	git clean -Xdf -e !$(VENV) -e !.env
