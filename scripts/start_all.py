#!/usr/bin/env python3
"""
AI-DAX Cross-Platform Service Launcher.
Manages the concurrent lifecycle of the Workload Generator, Scheduler, and Dashboard.
Works reliably on Windows (PowerShell/CMD) and Linux/macOS (Bash).
"""

from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import sys
import time
from types import FrameType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aidax.launcher")


class ProcessManager:
    """Manages child processes for AI-DAX components with clean shutdown handling."""

    def __init__(
        self,
        enable_workload: bool = True,
        enable_scheduler: bool = True,
        enable_dashboard: bool = True,
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> None:
        self.enable_workload = enable_workload
        self.enable_scheduler = enable_scheduler
        self.enable_dashboard = enable_dashboard
        self.host = host
        self.port = port
        self.processes: list[subprocess.Popen] = []
        self._shutting_down = False

    def start(self) -> None:
        """Spawn all enabled services."""
        py = sys.executable

        if self.enable_workload:
            logger.info("Spawning Workload Generator...")
            p_workload = subprocess.Popen([py, "-m", "aidax.workload", "--infinite"])
            self.processes.append(p_workload)

        if self.enable_scheduler:
            logger.info("Spawning LinUCB CPU Scheduler...")
            p_scheduler = subprocess.Popen([py, "-m", "aidax.scheduler"])
            self.processes.append(p_scheduler)

        if self.enable_dashboard:
            logger.info("Spawning FastAPI Dashboard on http://%s:%d...", self.host, self.port)
            p_api = subprocess.Popen(
                [
                    py,
                    "-m",
                    "uvicorn",
                    "aidax.api:app",
                    "--host",
                    self.host,
                    "--port",
                    str(self.port),
                ]
            )
            self.processes.append(p_api)

    def stop_all(self) -> None:
        """Gracefully terminate all running subprocesses."""
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("Stopping all AI-DAX services...")

        for p in self.processes:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass

        # Give processes a grace period to terminate
        time.sleep(0.5)

        for p in self.processes:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass
        logger.info("All services stopped.")

    def wait(self) -> None:
        """Wait for child processes or interrupt."""
        try:
            while any(p.poll() is None for p in self.processes):
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            self.stop_all()


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-DAX Unified Cross-Platform Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Dashboard port (default: 8000)")
    parser.add_argument(
        "--no-workload", action="store_true", help="Do not spawn workload generator"
    )
    parser.add_argument("--no-scheduler", action="store_true", help="Do not spawn AI scheduler")
    parser.add_argument(
        "--no-dashboard", action="store_true", help="Do not spawn FastAPI dashboard"
    )

    args = parser.parse_args()

    manager = ProcessManager(
        enable_workload=not args.no_workload,
        enable_scheduler=not args.no_scheduler,
        enable_dashboard=not args.no_dashboard,
        host=args.host,
        port=args.port,
    )

    def handle_signal(sig: int, frame: FrameType | None) -> None:
        logger.info("Signal %s received; initiating shutdown.", sig)
        manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    manager.start()
    manager.wait()


if __name__ == "__main__":
    main()
