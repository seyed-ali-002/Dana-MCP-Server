#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / ".dana.pid"

def is_dana_process(pid: int) -> bool:
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
        return "dana.main" in cmdline
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False

def main() -> int:
    if not PID_FILE.exists():
        print("Dana is not running.")
        return 0
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_FILE.unlink(missing_ok=True)
        print("Dana is not running.")
        return 0
    if not is_dana_process(pid):
        PID_FILE.unlink(missing_ok=True)
        print("Dana is not running (stale PID removed).")
        return 0
    print(f"Stopping Dana (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        print("Dana stopped.")
        return 0
    for _ in range(30):
        if not is_dana_process(pid):
            break
        time.sleep(0.1)
    if is_dana_process(pid):
        print("Dana did not stop within 3 seconds. Send Ctrl+C in its terminal or inspect the process manually.")
        return 1
    PID_FILE.unlink(missing_ok=True)
    print("Dana stopped.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
