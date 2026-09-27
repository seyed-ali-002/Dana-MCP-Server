from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .config import settings
from .installer import configure_tailscale_local, _ensure_tailscale_ready, _tailscale_hostname_from_status, command_exists, set_local_public_host, write_env

TAILSCALE_DOWNLOAD = "https://tailscale.com/download"
TAILSCALE_PACKAGES = "https://pkgs.tailscale.com/stable/"
TAILSCALE_INSTALL_SCRIPT = "https://tailscale.com/install.sh"

@dataclass
class SetupStatus:
    tailscale_installed: bool
    tailscale_backend: str
    tailscale_hostname: str
    funnel_active: bool
    funnel_hostname: str
    dana_running: bool
    mcp_url: str
    action_required: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

def _run(command: list[str], timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)

def _open(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass

def _find_auth_url(text: str) -> str | None:
    match = re.search(r"https://login\.tailscale\.com/[A-Za-z0-9_/?=&.-]+", text)
    return match.group(0) if match else None

def _find_funnel_hostname(value: object) -> str | None:
    if isinstance(value, dict):
        for key in value:
            found = _find_funnel_hostname(key)
            if found: return found
        for child in value.values():
            found = _find_funnel_hostname(child)
            if found: return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _find_funnel_hostname(child)
            if found: return found
    elif isinstance(value, str):
        match = re.search(r"\b([A-Za-z0-9._-]+\.ts\.net)\b", value)
        if match: return match.group(1)
    return None

def _funnel_hostname() -> str:
    try:
        result = _run(["tailscale", "funnel", "status", "--json"], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode: return ""
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    return _find_funnel_hostname(value) or _tailscale_hostname_from_status() or ""

def _funnel_active() -> bool:
    try:
        result = _run(["tailscale", "funnel", "status", "--json"], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode: return False
    text = result.stdout.lower()
    return "https://" in text and ("127.0.0.1" in text or str(settings.port) in text)

def _dana_running() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", settings.port), timeout=0.5):
            return True
    except OSError:
        return False

def status() -> SetupStatus:
    installed = command_exists("tailscale")
    backend = ""
    hostname = ""
    if installed:
        try:
            result = _run(["tailscale", "status", "--json"], timeout=8)
            if result.returncode == 0:
                payload = json.loads(result.stdout)
                backend = str(payload.get("BackendState", ""))
                hostname = str(payload.get("Self", {}).get("DNSName", "")).rstrip(".")
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
    funnel_host = _funnel_hostname() if installed else ""
    active = _funnel_active() if installed else False
    public_host = funnel_host if active else ""
    public_url = f"https://{public_host}/mcp" if public_host else "http://127.0.0.1:8765/mcp"
    action = ""
    message = ""
    if not installed:
        action, message = "install_tailscale", "Tailscale is not installed."
    elif backend.lower() != "running":
        action, message = "login_tailscale", "Tailscale needs to be connected."
    elif not _dana_running():
        action, message = "start_dana", "Dana is not running."
    elif not active:
        action, message = "enable_funnel", "Tailscale Funnel is not active."
    return SetupStatus(installed, backend, hostname, active, funnel_host, _dana_running(), public_url, action, message)

def verify_public_endpoint(host: str, timeout: float = 8.0) -> bool:
    import urllib.error
    url = f"https://{host}/mcp"
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "Dana-Setup/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status in {200, 401, 403, 405}
    except urllib.error.HTTPError as exc:
        return exc.code in {401, 403, 405}
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def install_tailscale() -> dict[str, object]:
    if command_exists("tailscale"):
        return {"ok": True, "installed": True, "message": "Tailscale is already installed."}
    system = platform.system().lower()
    if system == "linux":
        if not shutil.which("pkexec"):
            return {"ok": False, "action_required": "manual_install", "message": "A graphical privilege helper (pkexec) is required for a fully graphical Linux installation.", "url": TAILSCALE_DOWNLOAD}
        try:
            target = Path(tempfile.gettempdir()) / "tailscale-install.sh"
            urllib.request.urlretrieve(TAILSCALE_INSTALL_SCRIPT, target)
            result = _run(["pkexec", "sh", str(target)], timeout=240)
            if result.returncode != 0:
                return {"ok": False, "message": (result.stderr or result.stdout).strip()}
            return {"ok": command_exists("tailscale"), "message": "Tailscale installation finished."}
        except Exception as exc:
            return {"ok": False, "message": str(exc), "url": TAILSCALE_DOWNLOAD}
    if system == "windows": return _install_windows()
    if system == "darwin": return _install_macos()
    return {"ok": False, "action_required": "manual_install", "message": f"Unsupported OS: {system}", "url": TAILSCALE_DOWNLOAD}

def _stable_package_urls() -> tuple[str | None, str | None]:
    with urllib.request.urlopen(TAILSCALE_PACKAGES, timeout=15) as response:
        html = response.read().decode("utf-8", "replace")
    win = re.search(r'href="([^"]*tailscale-setup-[^"]+\.exe)"', html)
    mac = re.search(r'href="([^"]*Tailscale-[^"]+-macos\.pkg)"', html)
    def absolute(value: str | None) -> str | None:
        if not value: return None
        return value if value.startswith("http") else "https://pkgs.tailscale.com/stable/" + value.lstrip("/")
    return absolute(win.group(1) if win else None), absolute(mac.group(1) if mac else None)

def _install_windows() -> dict[str, object]:
    try:
        win_url, _ = _stable_package_urls()
        if not win_url: raise RuntimeError("Could not locate the current Tailscale Windows installer.")
        target = Path(tempfile.gettempdir()) / "tailscale-setup.exe"
        urllib.request.urlretrieve(win_url, target)
        import ctypes
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(target), None, None, 1)
        if result <= 32: raise RuntimeError("Windows elevation was cancelled or failed.")
        return {"ok": False, "pending": True, "message": "Tailscale installer opened. Finish the installer, then return to Dana.", "url": TAILSCALE_DOWNLOAD}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "url": TAILSCALE_DOWNLOAD}

def _install_macos() -> dict[str, object]:
    try:
        _, mac_url = _stable_package_urls()
        if not mac_url: raise RuntimeError("Could not locate the current Tailscale macOS installer.")
        target = Path(tempfile.gettempdir()) / "Tailscale.pkg"
        urllib.request.urlretrieve(mac_url, target)
        subprocess.Popen(["open", str(target)])
        return {"ok": False, "pending": True, "message": "Tailscale installer opened. Complete the installation and return to Dana.", "url": TAILSCALE_DOWNLOAD}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "url": TAILSCALE_DOWNLOAD}

def login_tailscale() -> dict[str, object]:
    if not command_exists("tailscale"):
        return {"ok": False, "action_required": "install_tailscale", "message": "Install Tailscale first."}
    result = _run(["tailscale", "up"], timeout=20)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    auth_url = _find_auth_url(output)
    if auth_url: _open(auth_url)
    if result.returncode == 0:
        return {"ok": True, "message": "Tailscale is connected.", "auth_url": auth_url or ""}
    return {"ok": False, "pending": bool(auth_url), "message": output.strip(), "auth_url": auth_url or ""}

def enable_funnel(port: int = 8765) -> dict[str, object]:
    if not command_exists("tailscale"):
        return {"ok": False, "action_required": "install_tailscale", "message": "Install Tailscale first."}
    try:
        _ensure_tailscale_ready()
    except RuntimeError as exc:
        return {"ok": False, "action_required": "login_tailscale", "message": str(exc)}
    try:
        host = configure_tailscale_local(settings.auth_token, port=port, funnel_port=443)
    except RuntimeError as exc:
        details = str(exc)
        auth_url = _find_auth_url(details)
        if auth_url:
            _open(auth_url)
            return {"ok": False, "pending": True, "action_required": "enable_funnel", "message": "Approve Funnel in the Tailscale browser flow, then return to Dana.", "auth_url": auth_url}
        return {"ok": False, "message": details}
    write_env("local", workers=settings.workers)
    set_local_public_host(host)
    verified = verify_public_endpoint(host)
    return {"ok": True, "hostname": host, "url": f"https://{host}/mcp", "endpoint_verified": verified, "message": "Dana MCP endpoint verified." if verified else "Funnel is active; MCP endpoint is still warming up."}

def start_dana() -> dict[str, object]:
    if _dana_running(): return {"ok": True, "message": "Dana is already running."}
    root = Path(__file__).resolve().parents[1]
    try:
        from . import container
        if container.is_available():
            container.start()
            return {"ok": True, "message": "Dana Docker runtime started."}
    except Exception:
        pass
    python = Path(os.environ["DANA_PYTHON"]) if os.environ.get("DANA_PYTHON") else Path(__import__("sys").executable)
    log = Path(os.getenv("DANA_RUNTIME_DIR", Path.home() / ".cache" / "dana")) / "gui-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log, "a", encoding="utf-8")
    if getattr(__import__("sys"), "frozen", False):
        command = [str(python), "--serve"]
    else:
        command = [str(python), "-m", "dana.main"]
    subprocess.Popen(command, cwd=root, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    return {"ok": True, "message": "Dana server is starting."}

def bootstrap(progress: Callable[[str], None] | None = None) -> dict[str, object]:
    progress = progress or (lambda _message: None)
    current = status()
    if not current.tailscale_installed:
        progress("Installing Tailscale")
        return install_tailscale()
    if current.tailscale_backend.lower() != "running":
        progress("Connecting Tailscale")
        return login_tailscale()
    if not current.dana_running:
        progress("Starting Dana")
        write_env("local", workers=settings.workers)
        result = start_dana()
        if not result.get("ok"):
            return result
        time.sleep(1)
    if not _funnel_active():
        progress("Enabling Tailscale Funnel")
        return enable_funnel(settings.port)
    return {"ok": True, "message": "Dana is ready.", "status": status().to_dict()}
