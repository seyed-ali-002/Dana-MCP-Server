#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    if platform.system().lower() == "windows":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def dana_listener_pids() -> set[int]:
    if platform.system().lower() == "windows":
        return set()
    try:
        result = subprocess.run(
            ["ss", "-ltnp", "sport = :8765"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        if "127.0.0.1:8765" not in line and "*:8765" not in line and "0.0.0.0:8765" not in line:
            continue
        for part in line.split():
            if "pid=" in part:
                try:
                    pids.add(int(part.split("pid=", 1)[1].split(",", 1)[0]))
                except ValueError:
                    pass
    return pids


def is_dana_process(pid: int) -> bool:
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
        return "dana.main" in cmdline
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False


def main() -> None:
    python = venv_python()
    if not python.exists():
        print("Dana is not installed.")
        print("Run python install.py first.")
        raise SystemExit(1)

    existing = sorted(pid for pid in dana_listener_pids() if pid > 0 and is_dana_process(pid))
    if existing:
        print(f"Dana is already running (PID {existing[0]}) on 127.0.0.1:8765.")
        return

    if not os.getenv("DANA_AUTH_TOKEN") and not (ROOT / ".env").exists():
        print("Dana is not configured.")
        print("Run python install.py first.")
        raise SystemExit(1)

    os.execv(str(python), [str(python), "-m", "dana.main"])


if __name__ == "__main__":
    main()
