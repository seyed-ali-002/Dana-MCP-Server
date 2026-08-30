from __future__ import annotations

import os

from rich.console import Console

from .main import run as run_server

console = Console()


def main() -> None:
    # Runtime only. Bootstrap/install logic lives in install.py -> dana.installer.
    if not os.environ.get("DANA_AUTH_TOKEN"):
        console.print("[bold red]Dana is not installed or configured.[/bold red]")
        console.print("Run [bold cyan]python install.py[/bold cyan] first.")
        raise SystemExit(1)
    run_server()


if __name__ == "__main__":
    main()

