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
from collections import deque
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .config import settings
from .installer import configure_tailscale_local, _ensure_tailscale_ready, _tailscale_hostname_from_status, command_exists, set_local_public_host, write_env

TAILSCALE_DOWNLOAD = "https://tailscale.com/download"
TAILSCALE_PACKAGES = "https://pkgs.tailscale.com/stable/"
TAILSCALE_INSTALL_SCRIPT = "https://tailscale.com/install.sh"

_SETUP_LOGS: deque[dict[str, str]] = deque(maxlen=250)
_DANA_PROCESS: subprocess.Popen[str] | None = None


def _setup_log(message: str, level: str = "info") -> None:
    _SETUP_LOGS.append({
        "time": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    })


def setup_logs() -> dict[str, object]:
    return {"logs": list(_SETUP_LOGS)}

@dataclass
class SetupStatus:
    tailscale_installed: bool
    tailscale_backend: str
    tailscale_hostname: str
    funnel_active: bool
    funnel_hostname: str
    dana_running: bool
    mcp_url: str
    local_mcp_url: str
    public_mcp_url: str
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

def _funnel_status() -> tuple[bool, str]:
    """Read Funnel state across Tailscale CLI schema/version differences."""
    try:
        result = _run(["tailscale", "funnel", "status", "--json"], timeout=10)
        raw = (result.stdout or "") + "\n" + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return False, ""

    hostname = ""
    try:
        value = json.loads(result.stdout)
        hostname = _find_funnel_hostname(value) or ""
    except json.JSONDecodeError:
        pass

    if not hostname:
        hostname = _find_funnel_hostname(raw) or _tailscale_hostname_from_status() or ""

    lowered = raw.lower()
    active = (
        result.returncode == 0
        and bool(hostname)
        and ("https://" in lowered or "available on the internet" in lowered)
        and ("127.0.0.1" in lowered or f":{settings.port}" in lowered or str(settings.port) in lowered)
    )
    if active:
        return True, hostname

    try:
        plain = _run(["tailscale", "funnel", "status"], timeout=10)
        text = (plain.stdout or "") + "\n" + (plain.stderr or "")
        plain_host = _find_funnel_hostname(text) or hostname
        plain_lower = text.lower()
        active = (
            plain.returncode == 0
            and bool(plain_host)
            and ("available on the internet" in plain_lower or "https://" in plain_lower)
            and ("127.0.0.1" in plain_lower or f":{settings.port}" in plain_lower or str(settings.port) in plain_lower)
        )
        return bool(active), plain_host if active else hostname
    except (OSError, subprocess.TimeoutExpired):
        return False, hostname

def _funnel_hostname() -> str:
    return _funnel_status()[1]

def _funnel_active() -> bool:
    return _funnel_status()[0]

def _dana_running(timeout: float = 0.5) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", settings.port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_for_dana(timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + max(0.5, timeout)
    while time.monotonic() < deadline:
        if _dana_running(timeout=0.75):
            return True
        time.sleep(0.25)
    return _dana_running(timeout=0.75)

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
    local_url = f"http://127.0.0.1:{settings.port}/mcp"
    public_url = f"https://{public_host}/mcp" if public_host else ""
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
    running = _dana_running()
    return SetupStatus(installed, backend, hostname, active, funnel_host, running, public_url or local_url, local_url, public_url, action, message)

def token_usage() -> dict[str, object]:
    """Read lightweight token totals for the desktop control center."""
    import sqlite3

    candidates: list[Path] = []
    for value in (
        os.getenv("DANA_ANALYTICS_PATH"),
        os.getenv("DANA_WORKSPACE"),
        os.getenv("DANA_ROOT"),
    ):
        if value:
            candidates.append(Path(value))
    try:
        candidates.append(Path.cwd())
    except OSError:
        pass
    candidates.extend([Path(__file__).resolve().parents[1], Path.home() / ".dana"])

    seen: set[Path] = set()
    for base in candidates:
        db = base if base.name == "analytics.db" else base / ".dana" / "analytics.db"
        try:
            db = db.resolve()
        except OSError:
            continue
        if db in seen or not db.is_file():
            continue
        seen.add(db)
        try:
            with sqlite3.connect(db, timeout=0.5) as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
                    "COALESCE(SUM(total_tokens),0), COUNT(*) FROM events"
                ).fetchone()
            return {
                "available": True,
                "input_tokens": int(row[0]),
                "output_tokens": int(row[1]),
                "total_tokens": int(row[2]),
                "operations": int(row[3]),
            }
        except (sqlite3.Error, OSError):
            continue
    return {"available": False, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "operations": 0}


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
    _setup_log("Starting Tailscale installation.")
    if command_exists("tailscale"):
        _setup_log("Tailscale is already installed.")
        return {"ok": True, "installed": True, "message": "Tailscale is already installed."}
    system = platform.system().lower()
    if system == "linux":
        if not shutil.which("pkexec"):
            return {"ok": False, "action_required": "manual_install", "message": "A graphical privilege helper (pkexec) is required for a fully graphical Linux installation.", "url": TAILSCALE_DOWNLOAD}
        try:
            target = Path(tempfile.gettempdir()) / "tailscale-install.sh"
            urllib.request.urlretrieve(TAILSCALE_INSTALL_SCRIPT, target)
            _setup_log("Launching the privileged Tailscale installer.")
            result = _run(["pkexec", "sh", str(target)], timeout=240)
            output = (result.stderr or result.stdout or "").strip()
            if result.returncode != 0:
                _setup_log("Tailscale installation failed: " + (output or f"installer exited with code {result.returncode}"), "error")
                return {"ok": False, "message": output or f"Installer exited with code {result.returncode}"}
            installed = command_exists("tailscale")
            _setup_log("Tailscale installation finished.", "success" if installed else "error")
            return {"ok": installed, "message": "Tailscale installation finished." if installed else "Tailscale was not found after installation."}
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
    _setup_log("Checking Tailscale authentication.")
    if not command_exists("tailscale"):
        _setup_log("Cannot authenticate because Tailscale is not installed.", "error")
        return {"ok": False, "action_required": "install_tailscale", "message": "Install Tailscale first."}
    result = _run(["tailscale", "up"], timeout=20)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    auth_url = _find_auth_url(output)
    if auth_url:
        _setup_log("Tailscale requested browser authentication. Opening the login page.")
        _open(auth_url)
    if result.returncode == 0:
        _setup_log("Tailscale authentication completed.", "success")
        return {"ok": True, "message": "Tailscale is connected.", "auth_url": auth_url or ""}
    details = output.strip() or f"tailscale up exited with code {result.returncode}"
    _setup_log("Tailscale authentication is pending." if auth_url else "Tailscale authentication failed: " + details, "warning" if auth_url else "error")
    return {"ok": bool(auth_url), "pending": bool(auth_url), "message": "Complete Tailscale authentication in the browser, then return to Dana." if auth_url else details, "auth_url": auth_url or ""}

def enable_funnel(port: int = 8765) -> dict[str, object]:
    _setup_log("Starting Tailscale Funnel setup.")
    if not command_exists("tailscale"):
        _setup_log("Cannot enable Funnel because Tailscale is not installed.", "error")
        return {"ok": False, "action_required": "install_tailscale", "message": "Install Tailscale first."}
    try:
        _ensure_tailscale_ready()
    except RuntimeError as exc:
        _setup_log("Tailscale is not ready for Funnel: " + str(exc), "error")
        return {"ok": False, "action_required": "login_tailscale", "message": str(exc)}
    try:
        host = configure_tailscale_local(settings.auth_token, port=port, funnel_port=443)
    except RuntimeError as exc:
        details = str(exc)
        auth_url = _find_auth_url(details)
        if auth_url:
            _setup_log("Tailscale requested Funnel approval in the browser. Opening the approval page.")
            _open(auth_url)
            return {"ok": True, "pending": True, "action_required": "enable_funnel", "message": "Approve Funnel in the Tailscale browser flow, then return to Dana.", "auth_url": auth_url}
        _setup_log("Funnel configuration failed: " + details, "error")
        return {"ok": False, "message": details}
    write_env("local", workers=settings.workers)
    set_local_public_host(host)
    verified = verify_public_endpoint(host)
    _setup_log(f"Funnel is active on {host}; endpoint verification: {'passed' if verified else 'pending'}.", "success" if verified else "warning")
    return {"ok": True, "hostname": host, "url": f"https://{host}/mcp", "endpoint_verified": verified, "message": "Dana MCP endpoint verified." if verified else "Funnel is active; MCP endpoint is still warming up."}

def start_dana() -> dict[str, object]:
    _setup_log("Starting Dana runtime.")
    if _dana_running():
        _setup_log("Dana runtime is already running.", "success")
        return {"ok": True, "message": "Dana is already running."}

    # The desktop sidecar is a self-contained PyInstaller runtime. Its extracted
    # bundle does not contain the source-tree Docker compose file, so Docker must
    # never be selected merely because Docker happens to be installed.
    root = Path(__file__).resolve().parents[1]
    docker_started = False
    try:
        from . import container
        if (
            not getattr(__import__("sys"), "frozen", False)
            and (root / "docker-compose.yml").is_file()
            and container.is_available()
        ):
            container.start()
            docker_started = True
            _setup_log("Dana Docker runtime started; waiting for readiness.")
            if _wait_for_dana(timeout=30.0):
                _setup_log("Dana Docker runtime is ready on the local MCP port.", "success")
                return {"ok": True, "message": "Dana is running."}
            _setup_log("Docker started but Dana did not become ready; falling back to the native runtime.", "warning")
    except Exception as exc:
        _setup_log(f"Docker runtime could not be started; using native runtime: {exc}", "warning")

    # Generate/preserve the local credential and explicitly pass it to the
    # bundled child. Installed builds cannot rely on a source-tree .env file.
    token = write_env("local", workers=settings.workers)
    os.environ["DANA_AUTH_TOKEN"] = token
    os.environ["DANA_DEPLOYMENT_MODE"] = "local"
    os.environ["DANA_HOST"] = "127.0.0.1"
    os.environ["DANA_PORT"] = str(settings.port)
    settings.auth_token = token

    python = Path(os.environ["DANA_PYTHON"]) if os.environ.get("DANA_PYTHON") else Path(__import__("sys").executable)
    log = Path(os.getenv("DANA_RUNTIME_DIR", Path.home() / ".cache" / "dana")) / "gui-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if getattr(__import__("sys"), "frozen", False):
        command = [str(python), "--serve"]
    else:
        command = [str(python), "-m", "dana.main"]
    _setup_log("Dana server process launched; waiting for the local MCP port.")
    global _DANA_PROCESS
    try:
        with open(log, "a", encoding="utf-8") as handle:
            _DANA_PROCESS = subprocess.Popen(
                command,
                cwd=root,
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as exc:
        _setup_log(f"Could not launch Dana runtime: {exc}", "error")
        return {"ok": False, "message": f"Could not launch Dana runtime: {exc}"}

    if _wait_for_dana(timeout=30.0):
        _setup_log("Dana runtime is ready on the local MCP port.", "success")
        return {"ok": True, "message": "Dana is running."}

    _setup_log("Dana runtime did not become ready within 30 seconds.", "error")
    return {
        "ok": False,
        "action_required": "start_dana",
        "message": "Dana did not become ready on the local MCP port within 30 seconds. Check the runtime log and try again.",
    }

def stop_dana() -> dict[str, object]:
    """Stop the Dana instance owned by the desktop setup flow."""
    global _DANA_PROCESS
    stopped = False

    if _DANA_PROCESS is not None:
        try:
            if _DANA_PROCESS.poll() is None:
                _DANA_PROCESS.terminate()
                try:
                    _DANA_PROCESS.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    _DANA_PROCESS.kill()
                    _DANA_PROCESS.wait(timeout=3)
                stopped = True
        except OSError as exc:
            _setup_log(f"Could not stop Dana runtime: {exc}", "error")
            return {"ok": False, "message": str(exc)}
        finally:
            _DANA_PROCESS = None

    try:
        from . import container
        root = Path(__file__).resolve().parents[1]
        if not getattr(__import__("sys"), "frozen", False) and (root / "docker-compose.yml").is_file() and container.is_available():
            container.stop()
            stopped = True
    except Exception:
        pass

    if _dana_running():
        _setup_log("Dana runtime is still listening after stop request.", "error")
        return {"ok": False, "message": "Dana could not be stopped cleanly."}

    _setup_log("Dana runtime stopped.", "success")
    return {"ok": True, "stopped": stopped, "message": "Dana is stopped."}


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
    if not _funnel_active():
        progress("Enabling Tailscale Funnel")
        return enable_funnel(settings.port)
    return {"ok": True, "message": "Dana is ready.", "status": status().to_dict()}
