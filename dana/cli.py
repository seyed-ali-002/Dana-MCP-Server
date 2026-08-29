from __future__ import annotations

import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
console = Console()


def clear() -> None:
    console.clear()


def banner(title: str = "DANA") -> None:
    console.print(
        Panel.fit(
            "[bold cyan]D A N A[/bold cyan]\n[dim]MCP Server Deployment Manager[/dim]",
            title=f"[bold]{title}[/bold]",
            border_style="cyan",
        )
    )


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def write_env(mode: str, public_host: str = "") -> str:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
    values["DANA_DEPLOYMENT_MODE"] = mode
    values["DANA_AUTH_TOKEN"] = values.get("DANA_AUTH_TOKEN") or secrets.token_urlsafe(32)
    if mode == "server":
        values["DANA_HOST"] = "127.0.0.1"
        values["DANA_PUBLIC_HOST"] = public_host
    env_path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    return values["DANA_AUTH_TOKEN"]


def install_python_dependencies() -> None:
    console.print("[cyan]Checking Python dependencies...[/cyan]")
    run_command([sys.executable, "-m", "pip", "install", "."], check=True)


def install_server_dependencies() -> None:
    if platform.system().lower() != "linux":
        raise RuntimeError("Server Mode is currently supported on Linux servers only.")
    if not command_exists("apt-get"):
        raise RuntimeError("Automatic server installation currently supports apt-based Linux distributions.")
    console.print("[cyan]Installing system dependencies...[/cyan]")
    run_command(["sudo", "apt-get", "update"])
    run_command(["sudo", "apt-get", "install", "-y", "caddy", "python3", "python3-venv"])


def configure_caddy(host: str) -> None:
    caddyfile = f"{host} {{\n    reverse_proxy 127.0.0.1:8765\n}}\n"
    tmp = Path("/tmp/dana.Caddyfile")
    tmp.write_text(caddyfile, encoding="utf-8")
    run_command(["sudo", "cp", str(tmp), "/etc/caddy/Caddyfile"])
    run_command(["sudo", "systemctl", "enable", "--now", "caddy"])
    run_command(["sudo", "systemctl", "reload", "caddy"])


def configure_service() -> None:
    service = f"""[Unit]\nDescription=Dana MCP Server\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory={ROOT}\nExecStart={sys.executable} -m dana.main\nRestart=always\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n"""
    tmp = Path("/tmp/dana.service")
    tmp.write_text(service, encoding="utf-8")
    run_command(["sudo", "cp", str(tmp), "/etc/systemd/system/dana.service"])
    run_command(["sudo", "systemctl", "daemon-reload"])
    run_command(["sudo", "systemctl", "enable", "--now", "dana"])


def install_local() -> None:
    console.print("[cyan]Preparing Local Mode...[/cyan]")
    install_python_dependencies()
    write_env("local")
    clear()
    banner("LOCAL MODE READY")
    console.print("[green]✓ Dependencies checked and installed[/green]")
    console.print("[green]✓ Local Mode configured[/green]")
    console.print("\nRun [bold cyan]python3 scripts/run.py[/bold cyan] to start Dana with Tailscale.")


def install_server() -> None:
    if os.geteuid() != 0 and not command_exists("sudo"):
        raise RuntimeError("Server Mode requires root privileges or sudo.")
    banner("SERVER MODE SETUP")
    console.print("[dim]Dana will configure a public MCP server with Caddy, HTTPS and systemd.[/dim]\n")
    host = Prompt.ask("[bold cyan]Domain[/bold cyan] (recommended)").strip().lower()
    if not host:
        raise RuntimeError("A domain is required for automatic HTTPS configuration.")
    console.print("\n[cyan]Starting server checks and installation...[/cyan]")
    install_server_dependencies()
    install_python_dependencies()
    console.print("[cyan]Configuring Dana Server Mode...[/cyan]")
    token = write_env("server", host)
    configure_caddy(host)
    configure_service()
    console.print("[cyan]Verifying service configuration...[/cyan]")
    run_command(["sudo", "systemctl", "is-active", "--quiet", "dana"])
    clear()
    banner("SERVER MODE READY")
    table = Table.grid(padding=(0, 2))
    table.add_row("STATUS", "[bold green]ONLINE[/bold green]")
    table.add_row("MODE", "[bold cyan]SERVER[/bold cyan]")
    table.add_row("MCP URL", f"[bold green]https://{host}/mcp[/bold green]")
    table.add_row("AUTH TOKEN", "[yellow]Saved in .env[/yellow]")
    table.add_row("SERVICE", "[green]systemd enabled[/green]")
    table.add_row("HTTPS", "[green]Managed by Caddy[/green]")
    console.print(Panel(table, border_style="green"))
    console.print(f"\n[bold cyan]Connector URL:[/bold cyan] https://{host}/mcp")
    console.print("[dim]The URL above is printed as one uninterrupted line for easy copying.[/dim]")
    console.print(f"[dim]Bearer token generated and stored securely in {ROOT / '.env'}[/dim]")
    _ = token


def main() -> None:
    clear()
    banner("INSTALLER")
    console.print("[bold]Select deployment mode[/bold]\n")
    console.print("[cyan]1[/cyan]  Local Device  [dim]Tailscale / personal computer[/dim]")
    console.print("[cyan]2[/cyan]  Public Server [dim]Domain + HTTPS + systemd[/dim]\n")
    choice = Prompt.ask("Choice", choices=["1", "2"], default="1")
    try:
        if choice == "1":
            install_local()
        else:
            install_server()
    except subprocess.CalledProcessError as exc:
        console.print(f"[bold red]Installation failed:[/bold red] {exc}")
        raise SystemExit(exc.returncode) from exc
    except Exception as exc:
        console.print(f"[bold red]Installation failed:[/bold red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
