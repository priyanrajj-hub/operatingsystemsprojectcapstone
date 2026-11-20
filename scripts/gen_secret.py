#!/usr/bin/env python3
"""
AI-DAX Secret Generator.
Generates cryptographically secure random tokens for API authentication,
session encryption, and internal webhook secrets.

Usage:
    python scripts/gen_secret.py
    python scripts/gen_secret.py --length 64 --format hex
"""

from __future__ import annotations

import argparse
import secrets


def generate_secret(n_bytes: int = 48, format_type: str = "urlsafe") -> str:
    """Generate cryptographically strong random token."""
    if format_type == "hex":
        return secrets.token_hex(n_bytes)
    return secrets.token_urlsafe(n_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate cryptographically secure tokens for AI-DAX configuration."
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=48,
        help="Number of random entropy bytes (default: 48 bytes -> 64 chars in base64url)",
    )
    parser.add_argument(
        "--format",
        choices=["urlsafe", "hex"],
        default="urlsafe",
        help="Token encoding format (urlsafe base64 or hex)",
    )
    parser.add_argument(
        "--for-env",
        action="store_true",
        help="Print in .env assignment format (AIDAX_API_TOKEN=<token>)",
    )

    args = parser.parse_args()
    token = generate_secret(n_bytes=args.bytes, format_type=args.format)

    if args.for_env:
        print(f"AIDAX_API_TOKEN={token}")
    else:
        print(token)


if __name__ == "__main__":
    main()
