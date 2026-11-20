"""
Cryptographically verified checkpoint persistence for contextual bandit models.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from core.exceptions import CheckpointError
from scheduler.linucb import StableLinUCBBandit

logger = logging.getLogger("aidax.persistence.checkpoints")


class CheckpointManager:
    """Handles atomic, checksum-verified serialization and deserialization of scheduler models."""

    def __init__(self, checkpoints_dir: str = "data/checkpoints") -> None:
        self.checkpoints_dir = Path(checkpoints_dir)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(data: str) -> str:
        """Compute SHA-256 digest of serialized state."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def save_linucb(self, bandit: StableLinUCBBandit, model_id: str = "linucb_latest") -> str:
        """Atomically persist a StableLinUCBBandit instance to disk with checksum."""
        state: dict[str, Any] = {
            "model_type": "StableLinUCBBandit",
            "num_arms": bandit.num_arms,
            "context_dim": bandit.context_dim,
            "exploration_alpha": bandit.exploration_alpha,
            "total_decisions": bandit.total_decisions,
            "arms": [
                {
                    "d": arm.d,
                    "exploration_alpha": arm.exploration_alpha,
                    "ridge_lambda": arm.ridge_lambda,
                    "A": arm.A.tolist(),
                    "b": arm.b.tolist(),
                }
                for arm in bandit.arms
            ],
        }

        serialized = json.dumps(state, indent=2)
        checksum = self.compute_sha256(serialized)
        envelope = {
            "model_id": model_id,
            "checksum": checksum,
            "payload": state,
        }

        target_file = self.checkpoints_dir / f"{model_id}.json"
        temp_file = target_file.with_suffix(f".tmp_{os.getpid()}")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2)
            os.replace(temp_file, target_file)
            logger.info("Saved LinUCB checkpoint %s (SHA-256: %s)", target_file, checksum[:8])
            return str(target_file)
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def load_linucb(self, model_id: str = "linucb_latest") -> StableLinUCBBandit:
        """Load and verify a StableLinUCBBandit instance."""
        target_file = self.checkpoints_dir / f"{model_id}.json"
        if not target_file.exists():
            raise CheckpointError(f"Checkpoint file not found: {target_file}")

        try:
            with open(target_file, encoding="utf-8") as f:
                envelope = json.load(f)
        except Exception as e:
            raise CheckpointError(f"Failed to parse checkpoint JSON: {e}") from e

        if "checksum" not in envelope or "payload" not in envelope:
            raise CheckpointError("Malformed checkpoint envelope: missing checksum or payload")

        payload = envelope["payload"]
        serialized_payload = json.dumps(payload, indent=2)
        expected_checksum = envelope["checksum"]
        actual_checksum = self.compute_sha256(serialized_payload)

        if actual_checksum != expected_checksum:
            raise CheckpointError(
                f"Checksum mismatch: expected {expected_checksum[:8]}, computed {actual_checksum[:8]}"
            )

        if payload.get("model_type") != "StableLinUCBBandit":
            raise CheckpointError(f"Incompatible model type: {payload.get('model_type')}")

        import numpy as np

        bandit = StableLinUCBBandit(
            context_dim=payload["context_dim"],
            exploration_alpha=payload["exploration_alpha"],
            num_arms=payload["num_arms"],
        )
        bandit.total_decisions = payload.get("total_decisions", 0)

        arms_data = payload.get("arms", [])
        if len(arms_data) != bandit.num_arms:
            raise CheckpointError(f"Arms count mismatch: {len(arms_data)} vs {bandit.num_arms}")

        for i, arm_data in enumerate(arms_data):
            arm = bandit.arms[i]
            arm.A = np.array(arm_data["A"], dtype=np.float64)
            arm.b = np.array(arm_data["b"], dtype=np.float64)
            arm.ridge_lambda = arm_data.get("ridge_lambda", 1.0)
            arm.exploration_alpha = arm_data.get("exploration_alpha", bandit.exploration_alpha)
            arm._dirty = True

        logger.info("Successfully loaded and verified LinUCB model %s", model_id)
        return bandit
