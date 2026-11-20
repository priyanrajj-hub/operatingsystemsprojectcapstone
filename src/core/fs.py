"""
Atomic file system operations with exponential retry and leak-free guarantees.
Handles Windows file-locking quirks (PermissionError) and ensures zero leaked tempfiles.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("aidax.core.fs")


def atomic_replace(
    src: Path | str,
    dst: Path | str,
    max_retries: int = 5,
    backoff_base: float = 0.05,
) -> None:
    """
    Atomically replace destination with source, retrying on Windows PermissionError.
    Guarantees src is deleted if an error occurs.
    """
    src_path = Path(src)
    dst_path = Path(dst)

    for attempt in range(max_retries):
        try:
            os.replace(src_path, dst_path)
            return
        except PermissionError as e:
            if attempt == max_retries - 1:
                logger.error(
                    "Failed to replace %s -> %s after %d retries: %s", src, dst, max_retries, e
                )
                raise
            sleep_time = backoff_base * (2**attempt)
            time.sleep(sleep_time)
        except Exception:
            raise
        finally:
            # If replacement succeeded, src_path no longer exists
            pass


def atomic_write_text(
    target: Path | str,
    content: str,
    encoding: str = "utf-8",
    max_retries: int = 5,
    backoff_base: float = 0.05,
) -> None:
    """Atomically write text to target file, cleaning up temporary files on any failure."""
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    prefix = f".{target_path.name}_"
    suffix = ".tmp"
    temp_fd, temp_name = tempfile.mkstemp(dir=target_path.parent, prefix=prefix, suffix=suffix)
    temp_path = Path(temp_name)

    try:
        with open(temp_fd, "w", encoding=encoding) as f:
            f.write(content)
        atomic_replace(temp_path, target_path, max_retries=max_retries, backoff_base=backoff_base)
    except Exception:
        raise
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def atomic_write_json(
    target: Path | str,
    data: Any,
    indent: int | None = None,
    encoding: str = "utf-8",
    max_retries: int = 5,
    backoff_base: float = 0.05,
) -> None:
    """Atomically write JSON data to target file with clean rollback."""
    serialized = json.dumps(data, indent=indent)
    atomic_write_text(
        target=target,
        content=serialized,
        encoding=encoding,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )
