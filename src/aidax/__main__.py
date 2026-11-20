"""
AI-DAX Package Main Entry Point
===============================
Allows running submodules via `python -m aidax <command>`:
  scheduler — Launch the LinUCB bandit CPU scheduler
  workload  — Launch the workload generator
  eval      — Run the four-condition evaluation harness
  dashboard — Launch the FastAPI dashboard server
  analysis  — Analyze evaluation results
"""

from __future__ import annotations

import sys


def main() -> None:
    commands = {
        "scheduler": "aidax.scheduler:main",
        "workload": "aidax.workload:main",
        "eval": "aidax.evaluate:main",
        "dashboard": "aidax.api:run_server",
        "analysis": "aidax.analysis:main",
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("Usage: python -m aidax <command> [args...]")
        print("Available commands:")
        for cmd in commands:
            print(f"  {cmd:<12}")
        sys.exit(1)

    cmd = sys.argv.pop(1)
    module_name, func_name = commands[cmd].split(":")
    import importlib

    mod = importlib.import_module(module_name)
    getattr(mod, func_name)()


if __name__ == "__main__":
    main()
