.PHONY: venv install run eval test lint format clean help

VENV ?= .venv
PYTHON = $(VENV)/bin/python
ifeq ($(OS),Windows_NT)
    PYTHON = $(VENV)/Scripts/python.exe
endif

help:
	@echo "Available make targets:"
	@echo "  venv     - Create Python virtual environment at $(VENV)"
	@echo "  install  - Install package in editable mode with development dependencies"
	@echo "  run      - Start workload generator, scheduler, and dashboard"
	@echo "  eval     - Run evaluation harness"
	@echo "  test     - Run pytest with coverage"
	@echo "  lint     - Run ruff linter and mypy type checks"
	@echo "  format   - Run ruff code formatter"
	@echo "  clean    - Remove build artifacts, pycache, and temporary state"

venv:
	python3 -m venv $(VENV) || python -m venv $(VENV)

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,llm]"

run:
	$(PYTHON) -m aidax.workload &
	$(PYTHON) -m aidax.scheduler &
	$(PYTHON) -m uvicorn aidax.api:app --host 127.0.0.1 --port 8000

eval:
	$(PYTHON) -m aidax.evaluate --duration 60 --trials 5

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m mypy src

format:
	$(PYTHON) -m ruff format src tests

clean:
	git clean -Xdf -e !$(VENV) -e !.env
