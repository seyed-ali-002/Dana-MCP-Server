#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / ".dana.pid"
PORT = 8765

def is_dana_process(pid: int) -> bool:
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore")
        return "dana.main" in cmdline
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False

def find_port_pids(port: int) -> list[int]:
    target = f"0100007F:{port:04X}".upper()
    try:
        lines = Path("/proc/net/tcp").read_text().splitlines()[1:]
    except (FileNotFoundError, PermissionError):
        return []
    inodes = {line.split()[9] for line in lines if len(line.split()) > 9 and line.split()[1].upper().endswith(target) and line.split()[3] == "0A"}
    if not inodes:
        return []
    found = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for fd in (proc / "fd").iterdir():
                if fd.is_symlink() and fd.resolve().name.startswith("socket:"):
                    inode = fd.resolve().name[8:-1] if fd.resolve().name.startswith("socket:[") else ""
                    if inode in inodes:
                        found.append(int(proc.name)); break
        except (FileNotFoundError, PermissionError, OSError):
            continue
    return sorted(set(found))

def main() -> int:
    pids = []
    if PID_FILE.exists():
        try:
            pids.append(int(PID_FILE.read_text(encoding="utf-8").strip()))
        except ValueError:
            pass
    pids.extend(find_port_pids(PORT))
    pids = sorted(set(pid for pid in pids if pid > 0))
    dana_pids = [pid for pid in pids if is_dana_process(pid)]
    if not dana_pids:
        PID_FILE.unlink(missing_ok=True)
        print("Dana is not running.")
        return 0
    print(f"Stopping Dana ({len(dana_pids)} process{'es' if len(dana_pids) != 1 else ''})...")
    for pid in dana_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(40):
        if not any(is_dana_process(pid) for pid in dana_pids):
            PID_FILE.unlink(missing_ok=True)
            print("Dana stopped.")
            return 0
        time.sleep(0.1)
    print("Dana did not stop within 4 seconds.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
