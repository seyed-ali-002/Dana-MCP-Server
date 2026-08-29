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


def write_env(mode: str, public_host: str = "", public_port: int = 0) -> str:
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
        values.pop("DANA_PUBLIC_PORT", None)
    if not values.get("DANA_AUTH_TOKEN") or values.get("DANA_AUTH_TOKEN") == "GENERATE_WITH_SCRIPT":
        values["DANA_AUTH_TOKEN"] = secrets.token_urlsafe(32)
    if mode == "server":
        # Keep Dana on an isolated loopback port. The existing HTTPS reverse proxy
        # on the server owns ports 80/443 and forwards the public /mcp route here.
        values["DANA_HOST"] = "127.0.0.1"
        values["DANA_PORT"] = str(public_port)
        values["DANA_PUBLIC_HOST"] = public_host
        values["DANA_PUBLIC_PORT"] = "0"
        values["DANA_PUBLIC_SCHEME"] = "https"
    else:
        values.pop("DANA_PUBLIC_SCHEME", None)
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
    # Never install the local project through its PEP 517 build backend during
    # bootstrap: some minimal Python 3.12 venvs do not contain setuptools.
    # Installing the runtime requirements directly is sufficient because Dana
    # is launched from the repository root and this avoids build-backend errors.
    requirements = ROOT / "requirements.txt"
    run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    run_command([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
    return python


def install_server_dependencies() -> None:
    if platform.system().lower() != "linux":
        raise RuntimeError("Server Mode is currently supported on Linux servers only.")
    if not command_exists("apt-get"):
        raise RuntimeError("Automatic server installation currently supports apt-based Linux distributions.")
    console.print("[cyan]Installing system dependencies...[/cyan]")
    run_command(["sudo", "apt-get", "update"])
    run_command(["sudo", "apt-get", "install", "-y", "python3", "python3-venv", "python3-full", "ca-certificates"])


def is_ip_address(host: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def port_is_listening(port: int) -> bool:
    result = subprocess.run(
        ["sudo", "ss", "-ltn"],
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    output = result.stdout
    return f":{port} " in output or f":{port}\n" in output


def choose_public_port() -> int:
    default_port = 18080
    while True:
        raw = Prompt.ask("[bold cyan]Public port[/bold cyan]", default=str(default_port)).strip()
        try:
            port = int(raw)
        except ValueError:
            console.print("[yellow]Enter a valid numeric port.[/yellow]")
            continue
        if not 1024 <= port <= 65535:
            console.print("[yellow]Use a port between 1024 and 65535.[/yellow]")
            continue
        if port_is_listening(port):
            console.print(f"[yellow]Port {port} is already in use. Choose another port.[/yellow]")
            continue
        return port


def configure_service(python: Path) -> None:
    service = f"""[Unit]\nDescription=Dana MCP Server\nAfter=network.target\n\n[Service]\nType=simple\nWorkingDirectory={ROOT}\nExecStart={python} -m dana.main\nRestart=always\nRestartSec=3\n\n[Install]\nWantedBy=multi-user.target\n"""
    tmp = Path("/tmp/dana.service")
    tmp.write_text(service, encoding="utf-8")
    run_command(["sudo", "cp", str(tmp), "/etc/systemd/system/dana.service"])
    run_command(["sudo", "systemctl", "daemon-reload"])
    run_command(["sudo", "systemctl", "enable", "--now", "dana"])


def configure_nginx_proxy(public_host: str, backend_port: int) -> None:
    if not command_exists("nginx"):
        raise RuntimeError("Nginx is not installed; automatic HTTPS proxy setup requires an existing supported reverse proxy.")
    snippet = f"""# Dana MCP reverse-proxy include\nlocation = /mcp {{\n    proxy_pass http://127.0.0.1:{backend_port};\n    proxy_http_version 1.1;\n    proxy_set_header Host $host;\n    proxy_set_header X-Real-IP $remote_addr;\n    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n    proxy_set_header X-Forwarded-Proto https;\n    proxy_set_header Accept $http_accept;\n    proxy_buffering off;\n    proxy_read_timeout 3600s;\n}}\n"""
    tmp = Path("/tmp/dana-mcp-nginx.conf")
    tmp.write_text(snippet, encoding="utf-8")
    run_command(["sudo", "mkdir", "-p", "/etc/nginx/snippets"])
    run_command(["sudo", "cp", str(tmp), "/etc/nginx/snippets/dana-mcp.conf"])
    console.print("[yellow]Nginx detected. The Dana proxy snippet was installed at /etc/nginx/snippets/dana-mcp.conf.[/yellow]")
    console.print("[yellow]For safety, Dana does not rewrite an existing server block automatically. Include this snippet in the HTTPS server block for the selected domain, then reload Nginx.[/yellow]")


def configure_caddy_proxy(public_host: str, backend_port: int) -> None:
    if not command_exists("caddy"):
        raise RuntimeError("Caddy is not installed.")
    snippet = f"""# Dana MCP reverse-proxy snippet for {public_host}\n# Add inside the existing site block for {public_host}:\nhandle /mcp {{\n    reverse_proxy 127.0.0.1:{backend_port}\n}}\n"""
    tmp = Path("/tmp/dana-mcp-caddy.txt")
    tmp.write_text(snippet, encoding="utf-8")
    run_command(["sudo", "mkdir", "-p", "/etc/caddy/snippets"])
    run_command(["sudo", "cp", str(tmp), "/etc/caddy/snippets/dana-mcp.txt"])
    console.print("[yellow]Caddy detected. The Dana proxy snippet was installed at /etc/caddy/snippets/dana-mcp.txt.[/yellow]")
    console.print("[yellow]For safety, Dana does not overwrite the existing Caddyfile. Add the generated handle block to the selected site's HTTPS block, then reload Caddy.[/yellow]")


def configure_reverse_proxy(public_host: str, backend_port: int) -> None:
    if command_exists("nginx"):
        configure_nginx_proxy(public_host, backend_port)
        return
    if command_exists("caddy"):
        configure_caddy_proxy(public_host, backend_port)
        return
    raise RuntimeError(
        "No supported HTTPS reverse proxy was detected. Install/configure Nginx or Caddy for the public domain, then forward /mcp to Dana's loopback port."
    )






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
    console.print("[dim]Dana will configure a public MCP server on an isolated high port with systemd.[/dim]\n")
    host = Prompt.ask("[bold cyan]Public domain or IP[/bold cyan]").strip().lower()
    if not host:
        raise RuntimeError("A public domain or IP address is required.")
    if " " in host or "/" in host:
        raise RuntimeError("Enter only a domain or IP address, without protocol or path.")
    public_port = choose_public_port()
    console.print("\n[cyan]Starting server checks and installation...[/cyan]")
    install_server_dependencies()
    python = install_python_dependencies()
    console.print("[cyan]Configuring Dana Server Mode...[/cyan]")
    write_env("server", host, public_port)
    configure_service(python)
    console.print("[cyan]Preparing HTTPS reverse-proxy integration...[/cyan]")
    configure_reverse_proxy(host, public_port)
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
    console.print(Panel(table, border_style="green"))
    console.print(f"\n[bold cyan]Connector URL:[/bold cyan] {connector_url}")
    console.print("[dim]The URL above is printed as one uninterrupted line for easy copying.[/dim]")
    console.print(f"[dim]Backend listens only on 127.0.0.1:{public_port}; configure your existing HTTPS reverse proxy to forward /mcp to it.[/dim]")


def main() -> None:
    clear()
    banner("INSTALLER")
    console.print("[bold]Select deployment mode[/bold]\n")
    console.print("[cyan]1[/cyan]  Local Device  [dim]Tailscale / personal computer[/dim]")
    console.print("[cyan]2[/cyan]  Public Server [dim]Custom port + systemd[/dim]\n")
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
