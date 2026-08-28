#!/usr/bin/env python3
"""Backward-compatible entry point for first-time token creation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_token import ensure_token


if __name__ == "__main__":
    print(ensure_token())
