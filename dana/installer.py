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
    if shutil.which(name) is not None:
        return True
    if name in {"tailscale", "tailscaled"}:
        return _tailscale_binary(name) is not None
    return False

def _tailscale_binary(name: str = "tailscale") -> str | None:
    """Locate Tailscale even when the GUI process PATH is incomplete."""
    found = shutil.which(name)
    if found:
        return found
    system = platform.system().lower()
    candidates: list[str] = []
    if system == "windows":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        exe = "tailscale.exe" if name == "tailscale" else "tailscaled.exe"
        candidates = [
            str(Path(pf) / "Tailscale" / exe),
            str(Path(pf86) / "Tailscale" / exe),
            str(Path(local) / "Tailscale" / exe),
        ]
    elif system == "darwin":
        if name == "tailscale":
            candidates = [
                "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                "/usr/local/bin/tailscale",
                "/opt/homebrew/bin/tailscale",
            ]
        else:
            candidates = ["/usr/local/bin/tailscaled", "/opt/homebrew/bin/tailscaled"]
    else:
        candidates = [
            f"/usr/bin/{name}",
            f"/usr/local/bin/{name}",
            f"/snap/bin/{name}",
            f"/usr/sbin/{name}",
        ]
    for candidate in candidates:
        path_obj = Path(candidate)
        try:
            if path_obj.is_file() and os.access(path_obj, os.X_OK):
                return str(path_obj)
        except OSError:
            continue
    return None

def _tailscale_cmd(*args: str) -> list[str]:
    binary = _tailscale_binary("tailscale") or "tailscale"
    return [binary, *args]


def write_env(
    mode: str, public_host: str = "", public_port: int = 0, workers: int = 5
) -> str:
    env_path = ROOT / ".env"
    persistent_env_path = Path.home() / ".config" / "dana" / ".env"
    values: dict[str, str] = {}
    source_path = persistent_env_path if persistent_env_path.exists() else env_path
    if source_path.exists():
        raw_env = source_path.read_text(encoding="utf-8").replace("\\n", "\n")
        for line in raw_env.splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values["DANA_DEPLOYMENT_MODE"] = mode
    values["DANA_WORKERS"] = str(workers)
    if mode == "server" and (not values.get("DANA_PORT") or not values.get("DANA_PORT", "").isdigit()):
        values["DANA_PORT"] = "8765"
    values.pop("DANA_WORKER_SEED", None)
    if mode == "local":
        values.pop("DANA_PUBLIC_HOST", None)
        values["DANA_PUBLIC_PORT"] = "443"
        values["DANA_PUBLIC_SCHEME"] = "https"
    if not values.get("DANA_AUTH_TOKEN") or values.get("DANA_AUTH_TOKEN") == "GENERATE_WITH_SCRIPT":
        values["DANA_AUTH_TOKEN"] = secrets.token_urlsafe(32)
        # Initial installation is the only implicit creation point. Existing
        # installations are read from the persistent auth store above and never
        # regenerate on restart/setup.
    if mode == "server":
        values["DANA_HOST"] = "127.0.0.1"
        values["DANA_PORT"] = str(public_port)
        values["DANA_PUBLIC_HOST"] = public_host
        values["DANA_PUBLIC_PORT"] = "0"
        values["DANA_PUBLIC_SCHEME"] = "https"
    else:
        values.pop("DANA_PUBLIC_SCHEME", None)
        values["DANA_HOST"] = values.get("DANA_HOST") or "127.0.0.1"
    rendered = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    persistent_env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(rendered, encoding="utf-8")
    persistent_env_path.write_text(rendered, encoding="utf-8")
    return values["DANA_AUTH_TOKEN"]


def venv_python() -> Path:
    venv = ROOT / ".venv"
    if platform.system().lower() == "windows":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def check_python_compatibility() -> None:
    version = sys.version_info[:2]
    if version < (3, 11):
        raise RuntimeError("Dana requires Python 3.11 or newer.")
    if version > (3, 13):
        console.print(
            f"[yellow]Warning: Python {platform.python_version()} is not in Dana's tested 3.11-3.13 range. Installation will continue, but use Python 3.12/3.13 if this machine shows compatibility issues.[/yellow]"
        )


def ensure_venv() -> Path:
    check_python_compatibility()
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




def _privileged_command(command: list[str]) -> list[str]:
    """Prefix a system package command with sudo only when needed."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return command
    if not command_exists("sudo"):
        raise RuntimeError("Installing Dana system dependencies requires root privileges or sudo.")
    return ["sudo", *command]


def _native_tool_requirements() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Return command requirements and package mappings for native Dana tools.

    Only packages corresponding to missing commands are sent to the package manager.
    Existing commands and known alternatives therefore never trigger reinstallations.
    """
    requirements = {
        "xdotool": "X11 desktop mouse/keyboard control",
        "ydotool": "Wayland desktop mouse/keyboard control",
        "ydotoold": "Wayland input daemon",
        "wl-copy": "Wayland clipboard write",
        "wl-paste": "Wayland clipboard read",
        "wmctrl": "desktop window control",
        "gnome-screenshot": "desktop screenshots",
        "ffmpeg": "media conversion and frame extraction",
        "ffprobe": "media inspection",
        "magick": "image resizing",
        "pdfinfo": "PDF metadata inspection",
        "tesseract": "OCR",
        "ssh": "SSH remote execution",
        "scp": "SSH file transfer",
        "docker": "Docker automation",
        "node": "Node.js runtime for web tooling",
        "npm": "Node.js package manager",
        "npx": "Node.js package runner",
        "ping": "network diagnostics",
        "ip": "network interface diagnostics",
    }
    packages = {
        "apt": {
            "xdotool": "xdotool", "ydotool": "ydotool", "ydotoold": "ydotoold", "wl-copy": "wl-clipboard", "wl-paste": "wl-clipboard", "wmctrl": "wmctrl", "gnome-screenshot": "gnome-screenshot",
            "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "magick": "imagemagick",
            "pdfinfo": "poppler-utils", "tesseract": "tesseract-ocr",
            "ssh": "openssh-client", "scp": "openssh-client", "docker": "docker.io",
            "node": "nodejs", "npm": "npm", "npx": "npm", "ping": "iputils-ping", "ip": "iproute2",
        },
        "dnf": {
            "xdotool": "xdotool", "ydotool": "ydotool", "ydotoold": "ydotoold", "wl-copy": "wl-clipboard", "wl-paste": "wl-clipboard", "wmctrl": "wmctrl", "gnome-screenshot": "gnome-screenshot",
            "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "magick": "ImageMagick",
            "pdfinfo": "poppler-utils", "tesseract": "tesseract",
            "ssh": "openssh-clients", "scp": "openssh-clients", "docker": "docker",
            "node": "nodejs", "npm": "npm", "npx": "npm", "ping": "iputils", "ip": "iproute",
        },
        "yum": {
            "xdotool": "xdotool", "ydotool": "ydotool", "ydotoold": "ydotoold", "wl-copy": "wl-clipboard", "wl-paste": "wl-clipboard", "wmctrl": "wmctrl", "gnome-screenshot": "gnome-screenshot",
            "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "magick": "ImageMagick",
            "pdfinfo": "poppler-utils", "tesseract": "tesseract",
            "ssh": "openssh-clients", "scp": "openssh-clients", "docker": "docker",
            "node": "nodejs", "npm": "npm", "npx": "npm", "ping": "iputils", "ip": "iproute",
        },
        "pacman": {
            "xdotool": "xdotool", "ydotool": "ydotool", "ydotoold": "ydotoold", "wl-copy": "wl-clipboard", "wl-paste": "wl-clipboard", "wmctrl": "wmctrl", "gnome-screenshot": "gnome-screenshot",
            "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "magick": "imagemagick",
            "pdfinfo": "poppler", "tesseract": "tesseract", "ssh": "openssh", "scp": "openssh",
            "docker": "docker", "node": "nodejs", "npm": "npm", "npx": "npm",
            "ping": "iputils", "ip": "iproute2",
        },
        "zypper": {
            "xdotool": "xdotool", "ydotool": "ydotool", "ydotoold": "ydotoold", "wl-copy": "wl-clipboard", "wl-paste": "wl-clipboard", "wmctrl": "wmctrl", "gnome-screenshot": "gnome-screenshot",
            "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "magick": "ImageMagick",
            "pdfinfo": "poppler-tools", "tesseract": "tesseract-ocr",
            "ssh": "openssh-clients", "scp": "openssh-clients", "docker": "docker",
            "node": "nodejs", "npm": "npm", "npx": "npm", "ping": "iputils", "ip": "iproute2",
        },
        "apk": {
            "xdotool": "xdotool", "ydotool": "ydotool", "ydotoold": "ydotoold", "wl-copy": "wl-clipboard", "wl-paste": "wl-clipboard", "wmctrl": "wmctrl", "gnome-screenshot": "gnome-screenshot",
            "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "magick": "imagemagick",
            "pdfinfo": "poppler-utils", "tesseract": "tesseract-ocr",
            "ssh": "openssh-client", "scp": "openssh-client", "docker": "docker",
            "node": "nodejs", "npm": "npm", "npx": "npm", "ping": "iproute2", "ip": "iproute2",
        },
    }
    return requirements, packages


def configure_ydotool_service() -> None:
    """Configure a privileged ydotoold with a private per-user socket."""
    if platform.system().lower() != "linux" or not command_exists("ydotoold"):
        return
    if not command_exists("systemctl") or not command_exists("modprobe"):
        return

    uid = os.getuid() if hasattr(os, "getuid") else 0
    gid = os.getgid() if hasattr(os, "getgid") else 0
    daemon = shutil.which("ydotoold")
    runtime_dir = f"dana-ydotool-{uid}"
    socket_path = f"/run/{runtime_dir}/.ydotool_socket"
    unit_name = f"dana-ydotoold-{uid}.service"
    unit_path = Path.home() / ".config" / "dana" / unit_name
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(
        "[Unit]\n"
        "Description=Dana ydotoold Wayland input daemon\n"
        "After=graphical.target\n"
        "ConditionPathExists=/dev/uinput\n\n"
        "[Service]\n"
        "ExecStartPre=/sbin/modprobe uinput\n"
        "Type=simple\n"
        "User=root\n"
        "RuntimeDirectory=" + runtime_dir + "\n"
        "RuntimeDirectoryMode=0755\n"
        f"ExecStart={daemon} --socket-path={socket_path} --socket-perm=0600 --socket-own={uid}:{gid}\n"
        "Restart=on-failure\n"
        "RestartSec=2\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n",
        encoding="utf-8",
    )
    target = Path("/etc/systemd/system") / unit_name
    try:
        run_command(_privileged_command(["modprobe", "uinput"]))
        modules = Path.home() / ".config" / "dana" / "uinput.conf"
        modules.write_text("uinput\n", encoding="utf-8")
        run_command(_privileged_command(["install", "-m", "0644", str(modules), "/etc/modules-load.d/dana-uinput.conf"]))
        run_command(_privileged_command(["install", "-m", "0644", str(unit_path), str(target)]))
        run_command(_privileged_command(["systemctl", "daemon-reload"]))
        run_command(_privileged_command(["systemctl", "enable", "--now", unit_name]))
        success(f"Wayland input daemon configured: {unit_name}")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "ydotoold was installed but Dana could not configure its system service. "
            "Run the installer again with sudo access."
        ) from exc


def install_tool_dependencies() -> None:
    """Install native dependencies required by Dana's currently registered tools."""
    system = platform.system().lower()
    if system != "linux":
        success(
            f"Native Linux tool dependencies are not installed on {system}; "
            "the Python dependencies and browser runtime are handled separately"
        )
        return

    requirements, package_sets = _native_tool_requirements()

    def available(command: str) -> bool:
        if command_exists(command):
            return True
        return command == "magick" and command_exists("convert")

    missing_commands = [command for command in requirements if not available(command)]
    if not missing_commands:
        success("All native dependencies required by Dana tools are installed")
        configure_ydotool_service()
        return

    manager_name = next(
        (name for name in ("apt", "dnf", "yum", "pacman", "zypper", "apk") if command_exists(name)),
        None,
    )
    if manager_name is None:
        raise RuntimeError(
            "Dana could not find a supported Linux package manager. "
            "Install the missing native tool dependencies manually: "
            + ", ".join(missing_commands)
        )

    package_map = package_sets[manager_name]
    packages = list(dict.fromkeys(package_map[command] for command in missing_commands))
    step(
        "Installing only missing native dependencies: "
        + ", ".join(packages)
    )
    try:
        if manager_name == "apt":
            run_command(_privileged_command(["apt-get", "update"]))
            run_command(_privileged_command(["apt-get", "install", "-y", *packages]))
        elif manager_name == "dnf":
            run_command(_privileged_command(["dnf", "install", "-y", *packages]))
        elif manager_name == "yum":
            run_command(_privileged_command(["yum", "install", "-y", *packages]))
        elif manager_name == "pacman":
            run_command(_privileged_command(["pacman", "-S", "--noconfirm", *packages]))
        elif manager_name == "zypper":
            run_command(_privileged_command(["zypper", "--non-interactive", "install", *packages]))
        else:
            run_command(_privileged_command(["apk", "add", *packages]))
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Could not install all native Dana tool dependencies. "
            "The package manager returned an error; rerun the installer after fixing the package manager."
        ) from exc

    # Configure the Wayland input daemon after native packages are present.
    success("Native dependency installation completed")
    configure_ydotool_service()



def install_tailscale_dependency() -> None:
    """Install the Tailscale client when Dana's local deployment requires it."""
    if command_exists("tailscale"):
        success("Tailscale is already installed")
        return
    system = platform.system().lower()
    if system != "linux":
        raise RuntimeError("Dana Local Mode requires Tailscale to be installed on Linux hosts.")
    # Reuse Dana's existing setup installer, which handles privileged installation
    # and the supported Linux distributions. Authentication remains a separate step.
    from dana.setup import install_tailscale

    result = install_tailscale()
    if not result.get("ok") or not command_exists("tailscale"):
        raise RuntimeError("Tailscale installation did not complete successfully.")
    success("Tailscale client installed")


def install_desktop_dependencies() -> None:
    """Backward-compatible alias for the complete native tool dependency installer."""
    install_tool_dependencies()

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
        try:
            result = subprocess.run(
                command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=10
            )
        except subprocess.TimeoutExpired:
            continue
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


def _elevate_command(command: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    """Request OS elevation without capturing the password."""
    system = platform.system().lower()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)
    if system == "darwin":
        import shlex
        shell = " ".join(shlex.quote(part) for part in command)
        shell_as = shell.replace('\\', '\\\\').replace('"', '\\"')
        script = 'do shell script "' + shell_as + '" with administrator privileges'
        return subprocess.run(["osascript", "-e", script], cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)
    if system == "windows":
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)
    if shutil.which("pkexec"):
        elevated = subprocess.run(["pkexec", *command], cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)
        if elevated.returncode == 0 or not shutil.which("sudo"):
            return elevated
    if shutil.which("sudo"):
        return subprocess.run(["sudo", *command], cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)

def _run_tailscale(command: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    """Run Tailscale with a hard timeout and elevate Funnel administration when needed."""
    if command and command[0] == "tailscale":
        command = _tailscale_cmd(*command[1:])
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout
        )
        details = (result.stderr or result.stdout or "").lower()
        needs_elevation = result.returncode != 0 and any(
            marker in details
            for marker in (
                "permission",
                "access denied",
                "access is denied",
                "root",
                "daemon",
                "privilege",
                "operation not permitted",
                "must be run as",
            )
        )
        is_funnel = any(part == "funnel" for part in command)
        if needs_elevation or (result.returncode != 0 and is_funnel):
            elevated = _elevate_command(command, timeout=max(timeout, 90.0))
            if elevated.returncode == 0:
                return elevated
            if elevated.stderr or elevated.stdout:
                return elevated
        return result
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Tailscale did not respond in time. Open Tailscale, make sure you are signed in and online, "
            "then run `tailscale status` and retry."
        ) from exc

def _ensure_tailscale_ready() -> None:
    result = _run_tailscale(["tailscale", "status", "--json"], timeout=12)
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            "Tailscale is installed but not ready. Start the Tailscale application and sign in first"
            + (f": {details}" if details else ".")
        )
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Tailscale returned an invalid status response. Restart Tailscale and try again.") from exc
    backend_state = str(status.get("BackendState", ""))
    if backend_state and backend_state.lower() != "running":
        raise RuntimeError(
            f"Tailscale is not connected (state: {backend_state}). Sign in and wait until it is connected, then retry."
        )


def _tailscale_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip()


def _is_tailscale_listener_conflict(details: str) -> bool:
    text = details.lower()
    return ("listener already exists" in text or "foreground listener already exists" in text or ("already exists for port" in text and "listener" in text))


def _configure_funnel_command(token: str, port: int, funnel_port: int) -> subprocess.CompletedProcess[str]:
    # Dana exposes a canonical HTTPS origin. OAuth discovery requires sibling
    # /.well-known endpoints to be reachable, so never hide MCP behind a token path.
    return _run_tailscale(["tailscale", "funnel", f"--https={funnel_port}", "--yes", "--bg", str(port)], timeout=25)


def configure_tailscale_local(token: str, port: int = 8765, funnel_port: int = 443) -> str:
    """Configure Funnel and automatically recover from stale/conflicting listeners."""
    if not command_exists("tailscale"):
        raise RuntimeError("Tailscale is not installed or not in PATH. Install and sign in to Tailscale first.")
    step("Checking Tailscale connection")
    _ensure_tailscale_ready()
    step("Requesting Tailscale Funnel (this should take only a few seconds)")
    result = _configure_funnel_command(token, port, funnel_port)
    if result.returncode != 0 and _is_tailscale_listener_conflict(_tailscale_error(result)):
        step("Existing Tailscale Funnel listener detected; resetting Dana's Funnel configuration")
        reset = _run_tailscale(["tailscale", "funnel", "reset"], timeout=15)
        if reset.returncode != 0:
            details = _tailscale_error(reset)
            raise RuntimeError("Tailscale Funnel has a conflicting listener and automatic reset failed" + (f": {details}" if details else "."))
        step(f"Recreating Funnel automatically with `tailscale funnel {port}`")
        result = _run_tailscale(["tailscale", "funnel", f"--https={funnel_port}", "--yes", "--bg", str(port)], timeout=25)
    if result.returncode != 0:
        details = _tailscale_error(result)
        raise RuntimeError("Could not configure Tailscale Funnel. Make sure Funnel is enabled for this Tailnet and the Tailscale client is up to date" + (f": {details}" if details else "."))
    for attempt in range(6):
        hostname = _tailscale_hostname_from_status()
        if hostname:
            return hostname
        if attempt < 5:
            time.sleep(0.75)
    raise RuntimeError("Tailscale Funnel was configured, but its public hostname could not be determined. Check `tailscale funnel status` and confirm that Tailscale DNS is enabled.")


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
    rendered = "\n".join(lines) + "\n"
    env_path.write_text(rendered, encoding="utf-8")
    persistent_env_path = Path.home() / ".config" / "dana" / ".env"
    if persistent_env_path.exists():
        persistent_lines = []
        persistent_found = False
        for line in persistent_env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DANA_PUBLIC_HOST="):
                persistent_lines.append(f"DANA_PUBLIC_HOST={host}")
                persistent_found = True
            else:
                persistent_lines.append(line)
        if not persistent_found:
            persistent_lines.append(f"DANA_PUBLIC_HOST={host}")
        persistent_env_path.write_text("\n".join(persistent_lines) + "\n", encoding="utf-8")


def install_local() -> None:
    section(
        "LOCAL DEVICE",
        "Personal computer • Tailscale Funnel • isolated Python environment",
    )
    step("Checking Python environment")
    install_python_dependencies()
    success("Python environment ready")
    install_tool_dependencies()
    install_tailscale_dependency()
    workers = choose_workers()
    success(f"Worker pool configured: {workers}")
    token = write_env("local", workers=workers)
    step("Configuring secure Tailscale Funnel")
    public_host = configure_tailscale_local(token)
    set_local_public_host(public_host)
    success(f"Secure endpoint configured: https://{public_host}/{token}/mcp")

    clear()
    banner("INSTALLATION COMPLETE")
    table = Table.grid(padding=(0, 2))
    table.add_row("STATUS", "[bold green]READY[/bold green]")
    table.add_row("MODE", "[bold cyan]LOCAL[/bold cyan]")
    table.add_row("WORKERS", str(workers))
    table.add_row("PUBLIC HOST", public_host)
    table.add_row("MCP URL", f"https://{public_host}/{token}/mcp")

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
    install_tool_dependencies()
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
