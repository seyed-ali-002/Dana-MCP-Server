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
    return subprocess.run(command, check=check, text=True, cwd=ROOT)


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
    if mode == "local":
        values.pop("DANA_PUBLIC_HOST", None)
    if not values.get("DANA_AUTH_TOKEN") or values.get("DANA_AUTH_TOKEN") == "GENERATE_WITH_SCRIPT":
        values["DANA_AUTH_TOKEN"] = secrets.token_urlsafe(32)
    if mode == "server":
        values["DANA_HOST"] = "127.0.0.1"
        values["DANA_PUBLIC_HOST"] = public_host
    else:
        values["DANA_HOST"] = values.get("DANA_HOST") or "127.0.0.1"
    env_path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    return values["DANA_AUTH_TOKEN"]


def venv_python() -> Path:
    venv = ROOT / ".venv"
    if platform.system().lower() == "windows":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def ensure_venv() -> Path:
    python = venv_python()
    if python.exists():
        return python
    console.print("[cyan]Creating isolated Python environment...[/cyan]")
    if platform.system().lower() == "windows":
        if not command_exists("python") and not command_exists("python3"):
            raise RuntimeError("Python is required.")
    elif not command_exists("python3"):
        raise RuntimeError("python3 is required.")
    try:
        run_command([sys.executable, "-m", "venv", str(ROOT / ".venv")])
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Could not create .venv. On Debian/Ubuntu install python3-venv and python3-full, then rerun the installer.") from exc
    if not python.exists():
        raise RuntimeError(f"Virtual environment was not created correctly: {python}")
    return python


def install_python_dependencies() -> Path:
    console.print("[cyan]Checking Python dependencies...[/cyan]")
    python = ensure_venv()
    run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    run_command([str(python), "-m", "pip", "install", "--no-build-isolation", str(ROOT)], check=True)
    return python


def install_server_dependencies() -> None:
    if platform.system().lower() != "linux":
        raise RuntimeError("Server Mode is currently supported on Linux servers only.")
    if not command_exists("apt-get"):
        raise RuntimeError("Automatic server installation currently supports apt-based Linux distributions.")
    console.print("[cyan]Installing system dependencies...[/cyan]")
    run_command(["sudo", "apt-get", "update"])
    run_command(["sudo", "apt-get", "install", "-y", "caddy", "python3", "python3-venv", "python3-full", "ca-certificates"])


def is_ip_address(host: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def configure_caddy(host: str) -> None:
    caddyfile = f"{host} {{\n    reverse_proxy 127.0.0.1:8765\n}}\n"
    tmp = Path("/tmp/dana.Caddyfile")
    tmp.write_text(caddyfile, encoding="utf-8")
    run_command(["sudo", "cp", str(tmp), "/etc/caddy/Caddyfile"])
    run_command(["sudo", "systemctl", "enable", "--now", "caddy"])
    run_command(["sudo", "systemctl", "reload", "caddy"])


def configure_service(python: Path) -> None:
    service = f"""[Unit]\nDescription=Dana MCP Server\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory={ROOT}\nExecStart={python} -m dana.main\nRestart=always\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n"""
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
    runner = venv_python()
    console.print(f"\nRun [bold cyan]{runner} -m dana.main[/bold cyan] to start Dana.")


def install_server() -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0 and not command_exists("sudo"):
        raise RuntimeError("Server Mode requires root privileges or sudo.")
    banner("SERVER MODE SETUP")
    console.print("[dim]Dana will configure a public MCP server with Caddy, HTTPS and systemd.[/dim]\n")
    host = Prompt.ask("[bold cyan]Public domain or IP[/bold cyan]").strip().lower()
    if not host:
        raise RuntimeError("A public domain or IP address is required.")
    if " " in host or "/" in host:
        raise RuntimeError("Enter only a domain or IP address, without protocol or path.")
    console.print("\n[cyan]Starting server checks and installation...[/cyan]")
    install_server_dependencies()
    python = install_python_dependencies()
    console.print("[cyan]Configuring Dana Server Mode...[/cyan]")
    token = write_env("server", host)
    configure_caddy(host) if not is_ip_address(host) else None
    configure_service(python)
    console.print("[cyan]Verifying service configuration...[/cyan]")
    run_command(["sudo", "systemctl", "is-active", "--quiet", "dana"])
    clear()
    banner("SERVER MODE READY")
    table = Table.grid(padding=(0, 2))
    table.add_row("STATUS", "[bold green]ONLINE[/bold green]")
    table.add_row("MODE", "[bold cyan]SERVER[/bold cyan]")
    scheme = "http" if is_ip_address(host) else "https"
    table.add_row("MCP URL", f"[bold green]{scheme}://{host}/mcp[/bold green]")
    table.add_row("AUTH TOKEN", "[yellow]Saved in .env[/yellow]")
    table.add_row("SERVICE", "[green]systemd enabled[/green]")
    table.add_row("HTTPS", "[green]Managed by Caddy[/green]" if scheme == "https" else "[yellow]Not configured for direct IP[/yellow]")
    console.print(Panel(table, border_style="green"))
    connector_url = f"{scheme}://{host}/mcp"
    console.print(f"\n[bold cyan]Connector URL:[/bold cyan] {connector_url}")
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
