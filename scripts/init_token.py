#!/usr/bin/env python3
"""Create the initial Dana token without replacing an existing token."""
from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
KEY = "DANA_AUTH_TOKEN"
PLACEHOLDER = "GENERATE_WITH_SCRIPT"


def ensure_token() -> str:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    for line in lines:
        if line.startswith(f"{KEY}="):
            value = line.split("=", 1)[1].strip()
            if value and value != PLACEHOLDER:
                return value
            break
    token = secrets.token_urlsafe(48)
    output = [f"{KEY}={token}" if line.startswith(f"{KEY}=") else line for line in lines]
    if not any(line.startswith(f"{KEY}=") for line in lines):
        output.append(f"{KEY}={token}")
    ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")
    return token


if __name__ == "__main__":
    print(ensure_token())
