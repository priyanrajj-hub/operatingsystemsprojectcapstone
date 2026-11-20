"""
Centralized, validated configuration for AI-DAX.
Supports .env loading, strong typing, zero-leak representation, and startup validation.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Automatically load environment variables from root .env if present
load_dotenv()

logger = logging.getLogger("aidax.config")


def mask_secret(secret_val: str | None) -> str:
    """Mask a sensitive string to prevent accidental leakage in logs or prints."""
    if not secret_val:
        return "<unset>"
    if len(secret_val) <= 6:
        return "******"
    return f"{secret_val[:4]}...{secret_val[-2:]} (len={len(secret_val)})"


class Settings(BaseModel):
    """Runtime configuration settings for the AI-DAX engine."""

    # 1. Server & Networking
    host: str = Field(default_factory=lambda: os.environ.get("AIDAX_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.environ.get("AIDAX_PORT", "8000")))
    debug: bool = Field(
        default_factory=lambda: os.environ.get("AIDAX_DEBUG", "false").lower() == "true"
    )
    read_only_mode: bool = Field(
        default_factory=lambda: os.environ.get("AIDAX_READ_ONLY", "false").lower() == "true"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.environ.get(
                "AIDAX_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
            ).split(",")
            if origin.strip()
        ]
    )
    log_level: str = Field(
        default_factory=lambda: os.environ.get("AIDAX_LOG_LEVEL", "INFO").upper()
    )

    # 2. Security & Auth
    api_token: str = Field(
        default_factory=lambda: os.environ.get("AIDAX_API_TOKEN", "aidax-insecure-dev-token")
    )
    require_auth: bool = Field(
        default_factory=lambda: os.environ.get("AIDAX_REQUIRE_AUTH", "false").lower() == "true"
    )
    rate_limit_per_minute: int = Field(
        default_factory=lambda: int(os.environ.get("AIDAX_RATE_LIMIT_PER_MINUTE", "120"))
    )

    # 3. Third-Party AI Integration
    gemini_api_key: str = Field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # 4. Persistence & File Paths
    database_url: str = Field(
        default_factory=lambda: os.environ.get("AIDAX_DATABASE_URL", "sqlite+aiosqlite:///aidax.db")
    )
    checkpoint_dir: str = Field(
        default_factory=lambda: os.environ.get("AIDAX_CHECKPOINT_DIR", "checkpoints")
    )
    results_dir: str = Field(default_factory=lambda: os.environ.get("AIDAX_RESULTS_DIR", "results"))
    pid_file: str = Field(default_factory=lambda: os.environ.get("AIDAX_PID_FILE", "pids.txt"))
    log_file: str = Field(
        default_factory=lambda: os.environ.get("AIDAX_LOG_FILE", "scheduler_log.csv")
    )
    stats_file: str = Field(
        default_factory=lambda: os.environ.get("AIDAX_STATS_FILE", "bandit_stats.json")
    )

    # 5. Scheduler Hyperparameters
    alpha_reward: float = Field(
        default_factory=lambda: float(os.environ.get("AIDAX_ALPHA_REWARD", "0.7"))
    )
    beta_reward: float = Field(
        default_factory=lambda: float(os.environ.get("AIDAX_BETA_REWARD", "0.3"))
    )
    exploration: float = Field(
        default_factory=lambda: float(os.environ.get("AIDAX_EXPLORATION", "1.5"))
    )
    cold_start_threshold: int = Field(
        default_factory=lambda: int(os.environ.get("AIDAX_COLD_START_THRESHOLD", "20"))
    )
    p_core_energy_cost: float = Field(default=1.0)
    e_core_energy_cost: float = Field(default=0.3)
    invol_ctx_norm_divisor: float = Field(default=1000.0)
    cycle_interval_s: float = Field(default=1.0)

    def __repr__(self) -> str:
        """Safe string representation that redacts sensitive keys."""
        items = []
        for k, v in self.__dict__.items():
            if any(
                secret_term in k.lower() for secret_term in ["token", "key", "password", "secret"]
            ):
                items.append(f"{k}={mask_secret(str(v))}")
            else:
                items.append(f"{k}={v!r}")
        return f"Settings({', '.join(items)})"

    def __str__(self) -> str:
        return self.__repr__()

    def resolve_paths(self) -> None:
        """Ensure runtime directories exist."""
        Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        Path(self.results_dir).mkdir(parents=True, exist_ok=True)


class ConfigurationError(ValueError):
    """Raised when application configuration fails safety or validation criteria."""


def validate_settings(cfg: Settings) -> None:
    """Validate runtime configuration values and assert safety boundaries."""
    errors: list[str] = []

    # Validate Port
    if not (1 <= cfg.port <= 65535):
        errors.append(f"Invalid AIDAX_PORT={cfg.port}: must be between 1 and 65535.")

    # Validate Host
    if not cfg.host:
        errors.append("AIDAX_HOST cannot be empty.")

    # Validate Rate Limit
    if cfg.rate_limit_per_minute <= 0:
        errors.append(
            f"Invalid AIDAX_RATE_LIMIT_PER_MINUTE={cfg.rate_limit_per_minute}: must be > 0."
        )

    # Validate Log Level
    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if cfg.log_level not in valid_log_levels:
        errors.append(
            f"Invalid AIDAX_LOG_LEVEL='{cfg.log_level}': must be one of {valid_log_levels}."
        )

    # Validate Gemini API Key format if present
    if cfg.gemini_api_key:
        if (
            cfg.gemini_api_key.lower().startswith("your_")
            or "placeholder" in cfg.gemini_api_key.lower()
        ):
            logger.info("Placeholder GEMINI_API_KEY detected; disabling cloud LLM features.")
        elif not re.match(r"^[A-Za-z0-9-_.]+$", cfg.gemini_api_key):
            errors.append("GEMINI_API_KEY contains invalid characters.")

    # Validate Hyperparameters
    if not (0.0 <= cfg.alpha_reward <= 1.0):
        errors.append(f"Invalid alpha_reward={cfg.alpha_reward}: must be in [0.0, 1.0].")
    if not (0.0 <= cfg.beta_reward <= 1.0):
        errors.append(f"Invalid beta_reward={cfg.beta_reward}: must be in [0.0, 1.0].")
    if cfg.exploration < 0.0:
        errors.append(f"Invalid exploration={cfg.exploration}: must be non-negative.")

    if errors:
        raise ConfigurationError("Configuration Validation Failed:\n - " + "\n - ".join(errors))


settings = Settings()
settings.resolve_paths()
validate_settings(settings)
