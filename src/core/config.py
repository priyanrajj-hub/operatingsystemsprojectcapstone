"""
Centralized configuration for AI-DAX using Pydantic Settings / Dataclasses.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration settings for the AI-DAX engine."""

    # Server & Networking
    host: str = Field(default=os.environ.get("AIDAX_HOST", "127.0.0.1"))
    port: int = Field(default=int(os.environ.get("AIDAX_PORT", "8000")))
    debug: bool = Field(default=os.environ.get("AIDAX_DEBUG", "false").lower() == "true")
    read_only_mode: bool = Field(default=os.environ.get("AIDAX_READ_ONLY", "false").lower() == "true")

    # Security & Auth
    api_token: str = Field(default=os.environ.get("AIDAX_API_TOKEN", "aidax-insecure-dev-token"))
    require_auth: bool = Field(default=os.environ.get("AIDAX_REQUIRE_AUTH", "false").lower() == "true")
    cors_origins: list[str] = Field(default=["http://127.0.0.1:8000", "http://localhost:8000"])
    rate_limit_per_minute: int = Field(default=120)

    # Persistence
    database_url: str = Field(default=os.environ.get("AIDAX_DATABASE_URL", "sqlite+aiosqlite:///aidax.db"))
    checkpoint_dir: str = Field(default=os.environ.get("AIDAX_CHECKPOINT_DIR", "checkpoints"))
    results_dir: str = Field(default=os.environ.get("AIDAX_RESULTS_DIR", "results"))

    # State files
    pid_file: str = Field(default=os.environ.get("AIDAX_PID_FILE", "pids.txt"))
    log_file: str = Field(default=os.environ.get("AIDAX_LOG_FILE", "scheduler_log.csv"))
    stats_file: str = Field(default=os.environ.get("AIDAX_STATS_FILE", "bandit_stats.json"))

    # Scheduler Hyperparameters
    alpha_reward: float = Field(default=0.7)
    beta_reward: float = Field(default=0.3)
    exploration: float = Field(default=1.5)
    cold_start_threshold: int = Field(default=20)
    p_core_energy_cost: float = Field(default=1.0)
    e_core_energy_cost: float = Field(default=0.3)
    invol_ctx_norm_divisor: float = Field(default=1000.0)
    cycle_interval_s: float = Field(default=1.0)

    def resolve_paths(self) -> None:
        """Ensure runtime directories exist."""
        Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        Path(self.results_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.resolve_paths()
