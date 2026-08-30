#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    if platform.system().lower() == "windows":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def main() -> None:
    python = venv_python()
    if not python.exists():
        console.print("[bold red]Dana is not installed.[/bold red]")
        console.print("Run [bold cyan]python install.py[/bold cyan] first.")
        raise SystemExit(1)

    if not os.getenv("DANA_AUTH_TOKEN") and not (ROOT / ".env").exists():
        console.print("[bold red]Dana is not configured.[/bold red]")
        console.print("Run [bold cyan]python install.py[/bold cyan] first.")
        raise SystemExit(1)

    os.execv(str(python), [str(python), "-m", "dana.main"])


if __name__ == "__main__":
    main()
