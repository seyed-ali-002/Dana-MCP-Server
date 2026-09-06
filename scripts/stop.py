#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_PID_FILE = ROOT / ".dana.pid"


def runtime_pid_file() -> Path:
    configured = os.getenv("DANA_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured) / "dana.pid"
    return Path.home() / ".cache" / "dana" / "dana.pid"


def is_dana_process(pid: int) -> bool:
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
        return "dana.main" in cmdline
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False


def main() -> int:
    pid_file = runtime_pid_file()
    candidates = [pid_file, LEGACY_PID_FILE]
    pids: set[int] = set()
    for file in candidates:
        try:
            if file.exists():
                pids.add(int(file.read_text(encoding="utf-8").strip()))
        except (OSError, ValueError):
            continue

    dana_pids = [pid for pid in sorted(pids) if pid > 0 and is_dana_process(pid)]
    if not dana_pids:
        for file in candidates:
            try:
                file.unlink(missing_ok=True)
            except OSError:
                pass
        print("Dana is not running.")
        return 0

    print(f"Stopping Dana ({len(dana_pids)} process{'es' if len(dana_pids) != 1 else ''})...")
    denied = False
    for pid in dana_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            denied = True

    if denied:
        print("Some Dana processes belong to another user. Stop them with the owning user or sudo.")
        return 1

    for _ in range(50):
        if not any(is_dana_process(pid) for pid in dana_pids):
            for file in candidates:
                try:
                    file.unlink(missing_ok=True)
                except OSError:
                    pass
            print("Dana stopped.")
            return 0
        time.sleep(0.1)

    print("Dana did not stop within 5 seconds.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
