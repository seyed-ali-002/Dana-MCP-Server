#!/usr/bin/env python3
"""Generate and persist a new Dana authentication token."""
from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
KEY = "DANA_AUTH_TOKEN"


def regenerate() -> str:
    token = secrets.token_urlsafe(48)
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{KEY}="):
            output.append(f"{KEY}={token}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"{KEY}={token}")
    ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")
    return token


if __name__ == "__main__":
    print(regenerate())
