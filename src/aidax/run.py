"""Console entrypoint for launching all AI-DAX components."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path to invoke start_all
scripts_dir = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import start_all  # noqa: E402


def main() -> None:
    start_all.main()


if __name__ == "__main__":
    main()
