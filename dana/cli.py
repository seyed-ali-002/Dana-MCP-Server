from __future__ import annotations

import ipaddress
import os
import shutil
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


def _docker_env_ready() -> bool:
    env_path = ROOT / ".env"
    return env_path.exists() and bool(os.environ.get("DANA_AUTH_TOKEN") or any(
        line.startswith("DANA_AUTH_TOKEN=") and line.split("=", 1)[1].strip()
        for line in env_path.read_text(encoding="utf-8").splitlines()
    ))


def _docker_install() -> None:
    from . import container
    from .installer import write_env

    if not _docker_env_ready():
        workers = int(os.getenv("DANA_WORKERS", "5"))
        workers = max(1, min(workers, 128))
        write_env("local", workers=workers)
    console.print("[cyan]Building Dana container...[/cyan]")
    container.install()
    console.print("[cyan]Starting Dana...[/cyan]")
    container.start()
    console.print("[bold green]✓ Dana is running.[/bold green]")
    token = os.getenv("DANA_AUTH_TOKEN", "")
    console.print(f"[cyan]Local MCP:[/cyan] http://127.0.0.1:8765/{token}/mcp" if token else "[cyan]Local MCP:[/cyan] http://127.0.0.1:8765/mcp")

    console.print("[cyan]Configuring Tailscale Funnel...[/cyan]")
    _docker_connect()


def _docker_connect() -> None:
    from . import container
    from .installer import configure_tailscale_local, set_local_public_host

    if not _docker_env_ready():
        raise RuntimeError("Dana is not installed. Run 'dana install' first.")
    from .config import settings
    host = configure_tailscale_local(settings.require_auth_token(), port=8765)
    set_local_public_host(host)
    container.restart()
    token = settings.require_auth_token()
    console.print(f"[bold green]✓ Secure MCP endpoint:[/bold green] https://{host}/{token}/mcp")


def _full_start() -> None:
    """Install/start Dana and configure its public Funnel endpoint in one step."""
    from . import container
    if container.is_available():
        _docker_install()
        return
    # Native fallback: start the existing runtime, then configure Funnel if possible.
    from .installer import main as installer_main
    installer_main()
    if shutil.which("tailscale"):
        from .config import settings
        from .installer import configure_tailscale_local, set_local_public_host
        host = configure_tailscale_local(settings.require_auth_token(), port=settings.port)
        set_local_public_host(host)
        token = settings.require_auth_token()
        console.print(f"[bold green]✓ Secure MCP endpoint:[/bold green] https://{host}/{token}/mcp")

def launch_gui() -> None:
    """Launch the packaged Tauri desktop control center when available."""
    candidates = [
        ROOT / "ui" / "src-tauri" / "target" / "release" / ("Dana.exe" if os.name == "nt" else "Dana"),
        ROOT / "ui" / "src-tauri" / "target" / "release" / "bundle" / "appimage" / "Dana.AppImage",
    ]
    if sys.platform == "darwin":
        candidates.insert(0, ROOT / "ui" / "src-tauri" / "target" / "release" / "bundle" / "macos" / "Dana.app")
    for candidate in candidates:
        if candidate.exists():
            if candidate.suffix == ".app":
                subprocess.Popen(["open", str(candidate)])
            else:
                subprocess.Popen([str(candidate)], cwd=ROOT)
            return
    console.print("[yellow]Dana Desktop is not built in this checkout.[/yellow]")
    console.print("[dim]Build it with the Tauri pipeline in packaging/ or install the Dana Desktop package.[/dim]")
    raise SystemExit(1)




def _launch_gui() -> None:
    ui = ROOT / "ui"
    force_tauri = "--tauri" in sys.argv[2:] or os.getenv("DANA_GUI_ENGINE", "").lower() == "tauri"
    use_tauri = force_tauri or (
        ui.exists()
        and shutil.which("npm") is not None
        and shutil.which("cargo") is not None
        and "--native" not in sys.argv[2:]
    )
    if use_tauri:
        if not shutil.which("npm"):
            raise RuntimeError("Node.js/npm is required for the Tauri development GUI.")
        if not ui.exists():
            raise RuntimeError("Dana GUI sources are not installed.")
        subprocess.run(["npm", "run", "tauri", "dev"], cwd=ui, check=True)
        return
    try:
        from .gui import main as gui_main
    except SystemExit:
        raise
    except Exception as exc:
        raise RuntimeError("Dana GUI requires the optional GUI dependencies. Install with: pip install 'dana-mcp-server[gui]'") from exc
    gui_main()


def _native_action(command: str) -> bool:
    """Handle terminal lifecycle commands without requiring Docker."""
    from . import setup

    if command == "start":
        result = setup.start_dana()
    elif command == "stop":
        result = setup.stop_dana()
    elif command == "restart":
        stop_result = setup.stop_dana()
        if not stop_result.get("ok"):
            result = stop_result
        else:
            result = setup.start_dana()
    elif command == "status":
        status = setup.status().to_dict()
        console.print_json(data=status)
        return True
    elif command == "logs":
        logs = setup.setup_logs().get("logs", [])
        for entry in logs:
            console.print(str(entry))
        return True
    elif command == "connect":
        from .config import settings
        from .installer import configure_tailscale_local, set_local_public_host
        token = settings.require_auth_token()
        host = configure_tailscale_local(token, port=settings.port, funnel_port=443)
        set_local_public_host(host)
        console.print(f"[bold green]✓ Secure MCP endpoint:[/bold green] https://{host}/{token}{settings.mcp_path}")
        return True
    else:
        return False

    if not result.get("ok"):
        console.print(f"[bold red]✗ {result.get('message', 'Dana operation failed.')}[/bold red]")
        return False
    console.print(f"[bold green]✓ {result.get('message', 'Dana operation completed.')}[/bold green]")
    return True


def _handle_command(command: str) -> bool:
    from . import container

    native_ready = (ROOT / ".env").is_file()

    if command in {"gui", "setup"}:
        _launch_gui()
        return True
    if command in {"run", "start-all", "up"}:
        _full_start()
        return True
    if command == "install":
        if container.is_available():
            _docker_install()
        else:
            console.print("[yellow]Docker is unavailable; opening the native Dana installer.[/yellow]")
            from .installer import main as installer_main
            installer_main()
        return True
    if command == "connect":
        if native_ready:
            _native_action("connect")
        elif container.is_available():
            _docker_connect()
        else:
            raise RuntimeError("Dana is not installed or configured. Run 'dana install' first.")
        return True
    if command in {"start", "stop", "restart", "status", "logs"}:
        if native_ready:
            _native_action(command)
        elif container.is_available():
            if command == "start":
                container.start()
            elif command == "stop":
                container.stop()
            elif command == "restart":
                container.restart()
            elif command == "status":
                container.status()
            else:
                container.logs(follow="--follow" in sys.argv[2:] or "-f" in sys.argv[2:])
        else:
            raise RuntimeError("Dana is not installed or configured. Run 'dana install' first.")
        return True
    if command == "update":
        if container.is_available():
            container.update()
        else:
            console.print("[yellow]Docker is unavailable; native Dana does not use Docker for updates.[/yellow]")
            console.print("[dim]Update the Python package/repository, then restart Dana.[/dim]")
        return True
    if command == "uninstall":
        remove_data = "--purge" in sys.argv[2:]
        if container.is_available():
            container.uninstall(remove_data=remove_data)
        else:
            from .installer import uninstall
            uninstall(remove_data=remove_data)
        return True
    return False


def main() -> None:
    _reexec_inside_dana_venv()
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if command and _handle_command(command):
        return
    if command == "doctor":
        from .doctor import main as doctor_main
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        doctor_main()
        return
    if command in {"gui", "desktop"}:
        launch_gui()
        return
    if not os.environ.get("DANA_AUTH_TOKEN"):
        console.print("[bold red]Dana is not installed or configured.[/bold red]")
        console.print("Run [bold cyan]dana install[/bold cyan] first.")
        raise SystemExit(1)
    run_server()


if __name__ == "__main__":
    main()
