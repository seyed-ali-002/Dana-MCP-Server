#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
console = Console()


def clear() -> None:
    console.clear()


def section(title: str, detail: str = "") -> None:
    body = f"[bold bright_white]{title}[/bold bright_white]"
    if detail:
        body += f"\n[dim]{detail}[/dim]"
    console.print(Panel(body, border_style="cyan", padding=(0, 2)))


def success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")


def step(message: str) -> None:
    console.print(f"[bright_cyan]›[/bright_cyan] {message}")


def banner(title: str = "DANA") -> None:
    logo = Text("D A N A", style="bold bright_cyan", justify="center")
    subtitle = Text("MCP Server Deployment Manager", style="dim", justify="center")
    content = Text.assemble(logo, "\n", subtitle)
    console.print(
        Panel(
            Align.center(content),
            title=f"[bold bright_white]{title}[/bold bright_white]",
            border_style="bright_cyan",
            padding=(1, 6),
        )
    )


def run_command(
    command: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True, cwd=ROOT)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def write_env(
    mode: str, public_host: str = "", public_port: int = 0, workers: int = 5
) -> str:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        raw_env = env_path.read_text(encoding="utf-8")
        # Older installers could write literal \n separators. Normalize
        # those before parsing so one malformed line cannot swallow the file.
        raw_env = raw_env.replace("\\n", "\n")
        for line in raw_env.splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values["DANA_DEPLOYMENT_MODE"] = mode
    values["DANA_WORKERS"] = str(workers)
    if mode == "server" and (not values.get("DANA_PORT") or not values.get("DANA_PORT", "").isdigit()):
        values["DANA_PORT"] = "8765"
    # Worker names are derived from DANA_AUTH_TOKEN at runtime, so no
    # per-run random seed is persisted here.
    values.pop("DANA_WORKER_SEED", None)
    if mode == "local":
        values.pop("DANA_PUBLIC_HOST", None)
        values["DANA_PUBLIC_PORT"] = "8443"
    if (
        not values.get("DANA_AUTH_TOKEN")
        or values.get("DANA_AUTH_TOKEN") == "GENERATE_WITH_SCRIPT"
    ):
        values["DANA_AUTH_TOKEN"] = secrets.token_urlsafe(32)
    if mode == "server":
        values["DANA_HOST"] = "127.0.0.1"
        values["DANA_PORT"] = str(public_port)
        values["DANA_PUBLIC_HOST"] = public_host
        values["DANA_PUBLIC_PORT"] = "0"
        values["DANA_PUBLIC_SCHEME"] = "https"
    else:
        values.pop("DANA_PUBLIC_SCHEME", None)
        values["DANA_HOST"] = values.get("DANA_HOST") or "127.0.0.1"
    env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
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
        raise RuntimeError(
            "Could not create .venv. On Debian/Ubuntu install python3-venv and python3-full, then rerun the installer."
        ) from exc
    if not python.exists():
        raise RuntimeError(f"Virtual environment was not created correctly: {python}")
    return python


def install_python_dependencies() -> Path:
    console.print("[cyan]Checking Python dependencies...[/cyan]")
    python = ensure_venv()
    requirements = ROOT / "requirements.txt"
    run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    run_command(
        [str(python), "-m", "pip", "install", "-r", str(requirements)], check=True
    )
    return python


def install_server_dependencies() -> None:
    if platform.system().lower() != "linux":
        raise RuntimeError("Server Mode is currently supported on Linux servers only.")
    if not command_exists("apt-get"):
        raise RuntimeError(
            "Automatic server installation currently supports apt-based Linux distributions."
        )
    console.print("[cyan]Installing system dependencies...[/cyan]")
    run_command(["sudo", "apt-get", "update"])
    run_command(
        [
            "sudo",
            "apt-get",
            "install",
            "-y",
            "python3",
            "python3-venv",
            "python3-full",
            "ca-certificates",
        ]
    )


def port_is_listening(port: int) -> bool:
    result = subprocess.run(
        ["sudo", "ss", "-ltn"], text=True, capture_output=True, cwd=ROOT, check=False
    )
    output = result.stdout
    return f":{port} " in output or f":{port}\n" in output


def choose_public_port() -> int:
    default_port = 18080
    while port_is_listening(default_port):
        default_port += 1
    while True:
        raw = Prompt.ask(
            "[bold cyan]Dana backend port[/bold cyan]", default=str(default_port)
        ).strip()
        try:
            port = int(raw)
        except ValueError:
            console.print("[yellow]Enter a valid numeric port.[/yellow]")
            continue
        if not 1024 <= port <= 65535:
            console.print("[yellow]Use a port between 1024 and 65535.[/yellow]")
            continue
        if port_is_listening(port):
            console.print(
                f"[yellow]Port {port} is already in use. Choose another port.[/yellow]"
            )
            continue
        return port


def configure_service(python: Path) -> None:
    service = f"""[Unit]\nDescription=Dana MCP Server\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory={ROOT}\nEnvironmentFile={ROOT}/.env\nExecStart={python} -m dana.main\nRestart=always\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n"""
    tmp = Path("/tmp/dana.service")
    tmp.write_text(service, encoding="utf-8")
    run_command(["sudo", "cp", str(tmp), "/etc/systemd/system/dana.service"])
    run_command(["sudo", "systemctl", "daemon-reload"])
    run_command(["sudo", "systemctl", "enable", "dana"])
    run_command(["sudo", "systemctl", "restart", "dana"])


def configure_reverse_proxy(
    public_host: str, backend_port: int, origin_protocol: str
) -> None:
    from dana.deployment import ProxyTarget, apply_proxy, detect_proxy, install_caddy

    target = detect_proxy(public_host)
    if target is None:
        console.print("[yellow]No supported reverse proxy was detected.[/yellow]")
        install = Prompt.ask(
            "Install Caddy automatically?", choices=["y", "n"], default="n"
        )
        if install != "y":
            raise RuntimeError(
                "Installation cancelled: no reverse proxy is available and Caddy installation was not approved."
            )
        step("Installing Caddy (approved by user)")
        install_caddy()
        target = ProxyTarget("caddy", Path("/etc/caddy/Caddyfile"), public_host)
    else:
        success(
            f"Using existing {target.kind}; no additional proxy service will be installed"
        )

    cert = key = None
    if target.kind == "nginx" and target.created and origin_protocol == "https":
        console.print(
            "[yellow]A new Nginx HTTPS site needs an existing certificate; Dana will not install a certificate service without approval.[/yellow]"
        )
        cert = Prompt.ask("SSL certificate path").strip()
        key = Prompt.ask("SSL private key path").strip()
        if not cert or not key:
            raise RuntimeError(
                "Certificate and private-key paths are required for a new HTTPS Nginx site."
            )

    action = (
        "create a dedicated configuration"
        if target.created
        else "modify the existing domain configuration"
    )
    console.print(f"[cyan]Deployment action:[/cyan] {action}: {target.config}")
    console.print(f"[cyan]Origin protocol:[/cyan] {origin_protocol.upper()}")
    confirm = Prompt.ask("Apply this deployment plan?", choices=["y", "n"], default="n")
    if confirm != "y":
        raise RuntimeError(
            "Installation cancelled before changing reverse-proxy configuration."
        )
    backup_path = apply_proxy(target, backend_port, origin_protocol, cert, key)
    console.print("[green]✓ /mcp route configured automatically[/green]")
    if backup_path:
        console.print(f"[dim]Backup: {backup_path}[/dim]")


def choose_workers(default: int = 5) -> int:
    while True:
        raw = Prompt.ask(
            "[bold cyan]Number of Dana workers[/bold cyan]", default=str(default)
        ).strip()
        try:
            workers = int(raw)
            if not 1 <= workers <= 128:
                raise ValueError
            return workers
        except ValueError:
            console.print("[yellow]Enter a worker count between 1 and 128.[/yellow]")


def _find_ts_hostname(value: object) -> str | None:
    """Find a Tailscale DNS hostname in structured or textual command output."""
    if isinstance(value, dict):
        # Funnel status commonly stores the hostname in the Web object key,
        # e.g. "desktop.example.ts.net:443". Inspect keys as well as values.
        for key in value:
            if isinstance(key, str):
                found = _find_ts_hostname(key)
                if found:
                    return found
        # Prefer explicit DNS fields when available.
        for key in ("DNSName", "DNS", "dns_name", "hostname", "Hostname"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                found = _find_ts_hostname(candidate)
                if found:
                    return found
        for child in value.values():
            found = _find_ts_hostname(child)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _find_ts_hostname(child)
            if found:
                return found
    elif isinstance(value, str):
        match = re.search(r"https?://([A-Za-z0-9._-]+\.ts\.net)(?::\d+)?(?:/|$)", value)
        if match:
            return match.group(1)
        match = re.search(r"\b([A-Za-z0-9._-]+\.ts\.net)\b", value)
        if match:
            return match.group(1)
    return None


def _tailscale_hostname_from_status() -> str | None:
    """Resolve the local Tailscale DNS name with JSON first and text fallback."""
    commands = [
        ["tailscale", "funnel", "status", "--json"],
        ["tailscale", "status", "--json"],
        ["tailscale", "funnel", "status"],
    ]
    for command in commands:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False
        )
        raw = result.stdout or result.stderr
        if not raw:
            continue
        if command[-1] == "--json":
            try:
                found = _find_ts_hostname(json.loads(raw))
            except json.JSONDecodeError:
                found = None
            if found:
                return found
        found = _find_ts_hostname(raw)
        if found:
            return found
    return None


def configure_tailscale_local(token: str, port: int = 8765, funnel_port: int = 8443) -> str:
    """Configure Local Mode Funnel silently and return its stable hostname."""
    if not command_exists("tailscale"):
        raise RuntimeError("Tailscale is not installed or not in PATH.")

    result = subprocess.run(
        [
            "tailscale",
            "funnel",
            f"--https={funnel_port}",
            "--set-path",
            f"/{token}",
            "--bg",
            f"http://127.0.0.1:{port}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"Could not configure Tailscale Funnel{': ' + details if details else ''}"
        )

    # Funnel status can take a moment to become visible after --bg returns.
    # Retry instead of assuming the first status response contains the hostname.
    for attempt in range(4):
        hostname = _tailscale_hostname_from_status()
        if hostname:
            return hostname
        if attempt < 3:
            time.sleep(0.75)

    raise RuntimeError(
        "Tailscale Funnel was configured, but its public hostname could not be determined. "
        "Check `tailscale funnel status` and confirm that Tailscale DNS is enabled."
    )


def set_local_public_host(host: str) -> None:
    env_path = ROOT / ".env"
    lines: list[str] = []
    found = False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DANA_PUBLIC_HOST="):
            lines.append(f"DANA_PUBLIC_HOST={host}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"DANA_PUBLIC_HOST={host}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_local() -> None:
    section(
        "LOCAL DEVICE",
        "Personal computer • Tailscale Funnel • isolated Python environment",
    )
    step("Checking Python environment")
    install_python_dependencies()
    success("Python environment ready")
    workers = choose_workers()
    success(f"Worker pool configured: {workers}")
    token = write_env("local", workers=workers)
    step("Configuring secure Tailscale Funnel")
    public_host = configure_tailscale_local(token)
    set_local_public_host(public_host)
    success(f"Secure endpoint configured: https://{public_host}:8443/{token}/mcp")
    clear()
    banner("INSTALLATION COMPLETE")
    table = Table.grid(padding=(0, 2))
    table.add_row("STATUS", "[bold green]READY[/bold green]")
    table.add_row("MODE", "[bold cyan]LOCAL[/bold cyan]")
    table.add_row("WORKERS", str(workers))
    table.add_row("PUBLIC HOST", public_host)
    table.add_row("TRANSPORT", "[green]Tailscale Funnel + MCP[/green]")
    console.print(
        Panel(
            table,
            title="[bold green]DANA READY[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


def install_server() -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0 and not command_exists("sudo"):
        raise RuntimeError("Server Mode requires root privileges or sudo.")
    banner("SERVER MODE SETUP")
    console.print(
        "[dim]Dana will use an isolated localhost backend and automatically integrate /mcp with your existing HTTPS reverse proxy.[/dim]\n"
    )
    host = Prompt.ask("[bold cyan]Public domain[/bold cyan]").strip().lower()
    if not host:
        raise RuntimeError("A public domain is required for safe Server Mode setup.")
    if " " in host or "/" in host or re.fullmatch(r"\d+(?:\.\d+){3}", host):
        raise RuntimeError("Enter a domain name without protocol, path, or IP address.")

    cdn = (
        Prompt.ask("Is this domain behind a CDN?", choices=["y", "n"], default="n")
        == "y"
    )
    if cdn:
        origin_protocol = Prompt.ask(
            "CDN to origin protocol", choices=["http", "https"], default="https"
        )
    else:
        origin_protocol = "https"

    public_port = choose_public_port()
    workers = choose_workers()
    console.print("\n[cyan]Starting server checks and installation...[/cyan]")
    install_server_dependencies()
    python = install_python_dependencies()
    console.print("[cyan]Configuring Dana Server Mode...[/cyan]")
    write_env("server", host, public_port, workers)
    console.print("[cyan]Preparing reverse-proxy integration...[/cyan]")
    configure_reverse_proxy(host, public_port, origin_protocol)
    configure_service(python)
    console.print("[cyan]Verifying service configuration...[/cyan]")
    run_command(["sudo", "systemctl", "is-active", "--quiet", "dana"])
    clear()
    banner("SERVER MODE READY")
    table = Table.grid(padding=(0, 2))
    table.add_row("STATUS", "[bold green]ONLINE[/bold green]")
    table.add_row("MODE", "[bold cyan]SERVER[/bold cyan]")
    connector_url = f"https://{host}/mcp"
    table.add_row("MCP URL", f"[bold green]{connector_url}[/bold green]")
    table.add_row("AUTH", "[yellow]Handled by the MCP endpoint[/yellow]")
    table.add_row("SERVICE", "[green]systemd enabled[/green]")
    table.add_row("BACKEND PORT", str(public_port))
    table.add_row("TRANSPORT", "[green]HTTPS via existing reverse proxy[/green]")
    table.add_row("WORKERS", str(workers))
    console.print(Panel(table, border_style="green"))
    console.print(f"\n[bold cyan]Connector URL:[/bold cyan] {connector_url}")
    console.print(
        "[dim]The URL above is printed as one uninterrupted line for easy copying.[/dim]"
    )
    console.print(
        f"[dim]Backend listens only on 127.0.0.1:{public_port}; the existing HTTPS reverse proxy was configured automatically.[/dim]"
    )


def main() -> None:
    clear()
    banner("INSTALLER")
    console.print(
        Panel(
            "[bold white]Welcome to Dana[/bold white]\n[dim]A clean setup wizard for your MCP server.[/dim]\n\n[cyan]1[/cyan]  Local Device   [dim]Personal computer + Tailscale Funnel[/dim]\n[cyan]2[/cyan]  Public Server  [dim]Linux server + HTTPS + systemd[/dim]",
            title="[bold bright_cyan]DEPLOYMENT[/bold bright_cyan]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    console.print()
    choice = Prompt.ask(
        "[bold bright_cyan]Select deployment mode[/bold bright_cyan]",
        choices=["1", "2"],
        default="1",
    )
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
