from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from .main import run as run_server

ROOT = Path(__file__).resolve().parents[1]
console = Console()


def venv_python() -> Path:
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def ensure_venv() -> Path:
    python = venv_python()
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
    return python


def install_python_dependencies() -> None:
    python = ensure_venv()
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-e", "."], cwd=ROOT, check=True)


def port_is_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def write_env(mode: str, host: str, public_port: int = 0) -> Path:
    values = {
        "DANA_DEPLOYMENT_MODE": mode,
        "DANA_PUBLIC_HOST": host,
        "DANA_HOST": host,
        "DANA_PORT": str(public_port or 8765),
        "DANA_PUBLIC_PORT": "0",
        "DANA_PUBLIC_SCHEME": "https",
    }
    if mode == "server":
        values["DANA_HOST"] = "127.0.0.1"
    target = ROOT / ".env"
    existing = {}
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                existing[key] = value
    existing.update(values)
    target.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n", encoding="utf-8")
    return target


def configure_reverse_proxy(host: str, public_port: int) -> None:
    from .deployment import apply_proxy, detect_proxy

    target = detect_proxy(host)
    if target is None:
        raise RuntimeError("No supported reverse proxy detected.")
    apply_proxy(target, public_port, token=os.environ.get("DANA_AUTH_TOKEN") or None)


def install_server(host: str, public_port: int = 8765) -> str:
    write_env("server", host, public_port)
    connector_url = f"https://{host}/mcp"
    configure_reverse_proxy(host, public_port)
    return connector_url


def _reexec_inside_dana_venv() -> None:
    """Use Dana's installed runtime for commands launched with system Python."""
    python = venv_python()
    try:
        current = Path(sys.executable).resolve()
        target = python.resolve()
    except OSError:
        return
    if not target.exists() or current == target:
        return
    os.execv(str(target), [str(target), "-m", "dana", *sys.argv[1:]])


def main() -> None:
    _reexec_inside_dana_venv()
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        from .doctor import main as doctor_main
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        doctor_main()
        return
    if not os.environ.get("DANA_AUTH_TOKEN"):
        console.print("[bold red]Dana is not installed or configured.[/bold red]")
        console.print("Run [bold cyan]python install.py[/bold cyan] first.")
        raise SystemExit(1)
    run_server()


if __name__ == "__main__":
    main()
