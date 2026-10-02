from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import tarfile
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
TAILSCALE_INSTALL_SCRIPT_MIRROR = "https://raw.githubusercontent.com/tailscale/tailscale/main/scripts/installer.sh"
TAILSCALE_STATIC_MIRROR = "https://ts-mirror.xedge.cc/stable/static/"
TAILSCALE_STATIC_OFFICIAL = "https://pkgs.tailscale.com/stable/"
TAILSCALE_STATIC_GITHUB = "https://github.com/tailscale/tailscale/releases/download/"

_AUTH_FLOW = {"pending": False, "kind": "", "auth_url": "", "message": ""}
_AUTH_FLOW_LOCK = __import__("threading").Lock()


def _set_auth_flow(kind: str = "", auth_url: str = "", message: str = "", pending: bool = False) -> None:
    with _AUTH_FLOW_LOCK:
        _AUTH_FLOW.update(pending=pending, kind=kind, auth_url=auth_url, message=message)


def auth_flow_status() -> dict[str, object]:
    with _AUTH_FLOW_LOCK:
        return dict(_AUTH_FLOW)


_DOWNLOAD = {"active": False, "paused": False, "cancelled": False, "downloaded": 0, "total": 0, "speed": 0.0, "name": "", "message": ""}
_DOWNLOAD_LOCK = __import__("threading").Lock()
_DOWNLOAD_PAUSE = __import__("threading").Event()
_DOWNLOAD_PAUSE.set()
_DOWNLOAD_CANCEL = __import__("threading").Event()


def download_status() -> dict[str, object]:
    with _DOWNLOAD_LOCK:
        return dict(_DOWNLOAD)


def pause_download() -> dict[str, object]:
    with _DOWNLOAD_LOCK:
        if not _DOWNLOAD["active"]:
            return {"ok": False, "message": "No active download."}
        _DOWNLOAD["paused"] = True
        _DOWNLOAD["message"] = "Download paused."
    _DOWNLOAD_PAUSE.clear()
    _setup_log("Download paused.", "warning")
    return {"ok": True, "message": "Download paused."}


def resume_download() -> dict[str, object]:
    with _DOWNLOAD_LOCK:
        if not _DOWNLOAD["active"]:
            return {"ok": False, "message": "No active download."}
        _DOWNLOAD["paused"] = False
        _DOWNLOAD["message"] = "Downloading…"
    _DOWNLOAD_PAUSE.set()
    _setup_log("Download resumed.")
    return {"ok": True, "message": "Download resumed."}


def cancel_download() -> dict[str, object]:
    with _DOWNLOAD_LOCK:
        if not _DOWNLOAD["active"]:
            return {"ok": False, "message": "No active download."}
        _DOWNLOAD_CANCEL.set()
        _DOWNLOAD_PAUSE.set()
        _DOWNLOAD["cancelled"] = True
        _DOWNLOAD["paused"] = False
        _DOWNLOAD["message"] = "Cancelling download…"
    _setup_log("Download cancellation requested.", "warning")
    return {"ok": True, "message": "Download cancellation requested."}


def _download_file(url: str, target: Path, label: str) -> None:
    import urllib.error
    import urllib.request
    started = time.monotonic()
    downloaded = 0
    candidates = [url]
    if url == TAILSCALE_INSTALL_SCRIPT:
        candidates.append(TAILSCALE_INSTALL_SCRIPT_MIRROR)
    # A configured mirror may be either a URL prefix (preferred) or a mirror
    # root. Keep both forms so common GitHub proxy/mirror deployments work.
    mirror = os.getenv("DANA_TAILSCALE_MIRROR", "").strip().rstrip("/")
    if mirror and "tailscale.com" in url:
        candidates.insert(0, mirror + "/" + url)
        candidates.insert(1, mirror + "/" + url.rsplit("/", 1)[-1])
    proxy = os.getenv("DANA_TAILSCALE_PROXY", "").strip()
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()
    _DOWNLOAD_CANCEL.clear()
    _DOWNLOAD_PAUSE.set()
    with _DOWNLOAD_LOCK:
        _DOWNLOAD.update(active=True, paused=False, cancelled=False, downloaded=0, total=0, speed=0.0, name=label, message="Connecting…")
    _setup_log(f"Downloading {label} from {url}")
    temporary = target.with_suffix(target.suffix + ".part")
    try:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                _setup_log(f"Trying Tailscale download source: {candidate}")
                request = urllib.request.Request(candidate, headers={"User-Agent": "Dana-Setup/1"})
                with opener.open(request, timeout=30) as response:
                    total = int(response.headers.get("Content-Length") or 0)
                    with _DOWNLOAD_LOCK:
                        _DOWNLOAD["total"] = total
                        _DOWNLOAD["downloaded"] = 0
                        _DOWNLOAD["message"] = "Downloading…"
                    downloaded = 0
                    with open(temporary, "wb") as handle:
                        while True:
                            if _DOWNLOAD_CANCEL.is_set():
                                raise InterruptedError("Download cancelled by user")
                            _DOWNLOAD_PAUSE.wait()
                            if _DOWNLOAD_CANCEL.is_set():
                                raise InterruptedError("Download cancelled by user")
                            chunk = response.read(64 * 1024)
                            if not chunk:
                                break
                            handle.write(chunk)
                            downloaded += len(chunk)
                            elapsed = max(0.001, time.monotonic() - started)
                            with _DOWNLOAD_LOCK:
                                _DOWNLOAD["downloaded"] = downloaded
                                _DOWNLOAD["speed"] = downloaded / elapsed
                    temporary.replace(target)
                    if candidate != url:
                        _setup_log("Primary Tailscale download source was unavailable; fallback source succeeded.", "warning")
                    break
            except urllib.error.HTTPError as exc:
                last_error = exc
                _setup_log(f"Tailscale download source returned HTTP {exc.code}; trying the next source.", "warning")
                continue
            except (urllib.error.URLError, OSError) as exc:
                last_error = exc
                _setup_log("Tailscale download source failed; trying the next source.", "warning")
                continue
        else:
            raise RuntimeError(f"All Tailscale download sources failed: {last_error}")
        with _DOWNLOAD_LOCK:
            _DOWNLOAD.update(active=False, paused=False, message="Download complete.")
        _setup_log(f"Download completed: {label}", "success")
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        with _DOWNLOAD_LOCK:
            _DOWNLOAD["active"] = False
            _DOWNLOAD["paused"] = False
            if _DOWNLOAD_CANCEL.is_set():
                _DOWNLOAD["message"] = "Download cancelled."
            else:
                _DOWNLOAD["message"] = "Download failed."
        if _DOWNLOAD_CANCEL.is_set():
            _setup_log(f"Download cancelled: {label}", "warning")
        else:
            _setup_log(f"Download failed: {label}", "error")
        raise

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


# Desktop-control configuration is intentionally limited to known Dana settings.
_CONFIG_KEYS = (
    "DANA_HOST", "DANA_PORT", "DANA_LOG_LEVEL", "DANA_WORKERS", "DANA_MCP_PATH",
    "DANA_PUBLIC_HOST", "DANA_PUBLIC_PORT", "DANA_PUBLIC_SCHEME", "DANA_DEPLOYMENT_MODE",
    "DANA_OAUTH_ACCESS_TOKEN_TTL_SECONDS", "DANA_MAX_BODY_BYTES", "DANA_ALLOW_DANGEROUS_TOOLS",
    "DANA_ALLOWED_ORIGINS", "DANA_ALLOWED_PATHS", "DANA_DENIED_PATHS",
    "DANA_TAILSCALE_FUNNEL_ENABLED", "DANA_TAILSCALE_FUNNEL_CHECK_SECONDS",
    "DANA_TAILSCALE_MIRROR", "DANA_TAILSCALE_PROXY",
    "MCP_OAUTH_REDIRECT_URIS",
)


def _env_path() -> Path:
    return Path(os.getenv("DANA_ROOT", Path(__file__).resolve().parents[1])) / ".env"


def _persistent_env_path() -> Path:
    return Path.home() / ".config" / "dana" / ".env"


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").replace("\\\\n", "\\n").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_env() -> dict[str, str]:
    values = _read_env_file(_env_path())
    persistent = _read_env_file(_persistent_env_path())
    # The persistent store is authoritative for the credential. This prevents
    # an older installation .env from silently rotating/restoring a token.
    if persistent.get("DANA_AUTH_TOKEN"):
        values["DANA_AUTH_TOKEN"] = persistent["DANA_AUTH_TOKEN"]
    return values


def _write_env(values: dict[str, str]) -> None:
    rendered = "\\n".join(f"{key}={value}" for key, value in values.items()) + "\\n"
    path = _env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    persistent = _persistent_env_path()
    persistent.parent.mkdir(parents=True, exist_ok=True)
    persistent.write_text(rendered, encoding="utf-8")


def _masked_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "•" * len(token)
    return token[:4] + "•" * max(4, len(token) - 8) + token[-4:]


def configuration() -> dict[str, object]:
    env = _read_env()
    defaults = {
        "DANA_HOST": settings.host, "DANA_PORT": settings.port, "DANA_LOG_LEVEL": settings.log_level,
        "DANA_WORKERS": settings.workers, "DANA_MCP_PATH": settings.mcp_path,
        "DANA_PUBLIC_HOST": settings.public_host, "DANA_PUBLIC_PORT": settings.public_port,
        "DANA_PUBLIC_SCHEME": settings.public_scheme, "DANA_DEPLOYMENT_MODE": settings.deployment_mode,
        "DANA_OAUTH_ACCESS_TOKEN_TTL_SECONDS": settings.oauth_access_token_ttl_seconds,
        "DANA_MAX_BODY_BYTES": settings.max_body_bytes, "DANA_ALLOW_DANGEROUS_TOOLS": settings.allow_dangerous_tools,
        "DANA_ALLOWED_ORIGINS": settings.allowed_origins, "DANA_ALLOWED_PATHS": settings.allowed_paths,
        "DANA_DENIED_PATHS": settings.denied_paths, "DANA_TAILSCALE_FUNNEL_ENABLED": settings.tailscale_funnel_enabled,
        "DANA_TAILSCALE_FUNNEL_CHECK_SECONDS": settings.tailscale_funnel_check_seconds,
        "DANA_TAILSCALE_MIRROR": os.getenv("DANA_TAILSCALE_MIRROR", ""),
        "DANA_TAILSCALE_PROXY": os.getenv("DANA_TAILSCALE_PROXY", ""),
        "MCP_OAUTH_REDIRECT_URIS": "",
    }
    def _text(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
    values = {key: env[key] if key in env else _text(defaults.get(key, "")) for key in _CONFIG_KEYS if key != "DANA_AUTH_TOKEN"}
    return {
        "values": values,
        "defaults": {key: _text(defaults.get(key, "")) for key in _CONFIG_KEYS if key != "DANA_AUTH_TOKEN"},
        "auth_token": _masked_token(env.get("DANA_AUTH_TOKEN", settings.auth_token)),
        "auth_token_configured": bool(env.get("DANA_AUTH_TOKEN", settings.auth_token)),
        "keys": list(_CONFIG_KEYS),
    }


def update_configuration(values: dict[str, object]) -> dict[str, object]:
    was_running = _dana_running()
    env = _read_env()
    changed: list[str] = []
    for key, value in values.items():
        if key not in _CONFIG_KEYS:
            raise ValueError(f"Unsupported configuration key: {key}")
        if key == "MCP_OAUTH_REDIRECT_URIS":
            text = str(value).strip()
        elif isinstance(value, bool):
            text = "true" if value else "false"
        else:
            text = str(value).strip()
        if key in {"DANA_PORT", "DANA_WORKERS", "DANA_PUBLIC_PORT", "DANA_OAUTH_ACCESS_TOKEN_TTL_SECONDS", "DANA_MAX_BODY_BYTES", "DANA_TAILSCALE_FUNNEL_CHECK_SECONDS"}:
            if not text or not text.isdigit():
                raise ValueError(f"{key} must be a non-empty numeric value")
        if key in {"DANA_ALLOW_DANGEROUS_TOOLS", "DANA_TAILSCALE_FUNNEL_ENABLED"} and text.lower() not in {"true", "false"}:
            raise ValueError(f"{key} must be true or false")
        if key == "DANA_DEPLOYMENT_MODE" and text.lower() not in {"local", "server"}:
            raise ValueError("DANA_DEPLOYMENT_MODE must be local or server")
        if env.get(key, "") != text:
            env[key] = text
            changed.append(key)
    _write_env(env)
    field_map = {
        "DANA_HOST": ("host", str), "DANA_PORT": ("port", int), "DANA_LOG_LEVEL": ("log_level", str),
        "DANA_WORKERS": ("workers", int), "DANA_MCP_PATH": ("mcp_path", str), "DANA_PUBLIC_HOST": ("public_host", str),
        "DANA_PUBLIC_PORT": ("public_port", int), "DANA_PUBLIC_SCHEME": ("public_scheme", str),
        "DANA_DEPLOYMENT_MODE": ("deployment_mode", str), "DANA_OAUTH_ACCESS_TOKEN_TTL_SECONDS": ("oauth_access_token_ttl_seconds", int),
        "DANA_MAX_BODY_BYTES": ("max_body_bytes", int), "DANA_ALLOW_DANGEROUS_TOOLS": ("allow_dangerous_tools", lambda x: x.lower() == "true"),
        "DANA_ALLOWED_ORIGINS": ("allowed_origins", str), "DANA_ALLOWED_PATHS": ("allowed_paths", str), "DANA_DENIED_PATHS": ("denied_paths", str),
        "DANA_TAILSCALE_FUNNEL_ENABLED": ("tailscale_funnel_enabled", lambda x: x.lower() == "true"),
        "DANA_TAILSCALE_FUNNEL_CHECK_SECONDS": ("tailscale_funnel_check_seconds", int),
        "DANA_TAILSCALE_MIRROR": ("tailscale_mirror", str),
        "DANA_TAILSCALE_PROXY": ("tailscale_proxy", str),
    }
    for key in changed:
        if key.startswith("DANA_"):
            os.environ[key] = env[key]
        if key in field_map and env[key] != "":
            field, caster = field_map[key]
            try:
                setattr(settings, field, caster(env[key]))
            except (TypeError, ValueError):
                pass
    if "DANA_AUTH_TOKEN" in env:
        settings.auth_token = env["DANA_AUTH_TOKEN"]
    _setup_log(f"Configuration updated: {', '.join(changed) if changed else 'no changes'}", "success" if changed else "info")
    if changed and was_running:
        restart = _restart_runtime_preserving_funnel()
        if not restart.get("ok"):
            return {"ok": False, "changed": changed, "message": str(restart.get("message", "Dana restart failed.")), "configuration": configuration()}
    return {"ok": True, "changed": changed, "configuration": configuration()}


def _restart_runtime_preserving_funnel() -> dict[str, object]:
    was_funnel = _funnel_active()
    stop_result = stop_dana()
    if not stop_result.get("ok"):
        return stop_result
    result = start_dana()
    if result.get("ok") and was_funnel:
        funnel_result = enable_funnel(settings.port)
        if not funnel_result.get("ok") and not funnel_result.get("pending"):
            return funnel_result
    return result


def set_auth_token(token: str, *, revoke: bool = False) -> dict[str, object]:
    import secrets
    token = token.strip() if token else ""
    if revoke:
        token = secrets.token_urlsafe(32)
    if not token:
        raise ValueError("Token cannot be empty")
    if len(token) < 16 or len(token) > 256 or not re.fullmatch(r"[A-Za-z0-9._~-]+", token):
        raise ValueError("Token must be 16-256 characters and contain only letters, numbers, '.', '_', '-' or '~'.")
    env = _read_env()
    old = env.get("DANA_AUTH_TOKEN", settings.auth_token)
    env["DANA_AUTH_TOKEN"] = token
    _write_env(env)
    os.environ["DANA_AUTH_TOKEN"] = token
    settings.auth_token = token
    _setup_log("Authentication token revoked and replaced." if revoke else "Custom authentication token applied.", "warning" if revoke else "success")
    restart = _restart_runtime_preserving_funnel()
    if not restart.get("ok"):
        return {"ok": False, "message": restart.get("message", "Runtime restart failed."), "token": _masked_token(token)}
    return {"ok": True, "token": _masked_token(token), "connection_url": status().mcp_url, "message": "Authentication token rotated and Dana restarted." if revoke else "Custom authentication token applied and Dana restarted."}


def generate_auth_token() -> dict[str, object]:
    return set_auth_token(__import__("secrets").token_urlsafe(32), revoke=False)

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
    auth_token: str = ""
    action_required: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

def _run(command: list[str], timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)


def _privileged_run(command: list[str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
    """Run an administrative command without hiding the user's password prompt.

    Terminal sessions prefer sudo so the password is requested in the terminal.
    Desktop sessions prefer pkexec, which provides the native authentication dialog.
    The password is never captured or stored by Dana.
    """
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return _run(command, timeout=timeout)
    if shutil.which("sudo") and os.isatty(0):
        return _run(["sudo", *command], timeout=timeout)
    if shutil.which("pkexec"):
        result = _run(["pkexec", *command], timeout=timeout)
        if result.returncode == 0:
            return result
    if shutil.which("sudo"):
        return _run(["sudo", *command], timeout=timeout)
    raise RuntimeError("This operation requires administrator privileges, but neither pkexec nor sudo is available.")


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
    """Read Funnel state across current Tailscale CLI schemas."""
    try:
        result = _run(["tailscale", "funnel", "status", "--json"], timeout=10)
        raw = (result.stdout or "") + "\n" + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return False, ""

    payload: object = None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None

    hostname = _find_funnel_hostname(payload) or _find_funnel_hostname(raw) or ""
    if not hostname:
        hostname = _tailscale_hostname_from_status() or ""

    def contains_local_target(value: object) -> bool:
        text = json.dumps(value, ensure_ascii=False).lower() if not isinstance(value, str) else value.lower()
        return any(target in text for target in (
            f"http://127.0.0.1:{settings.port}",
            f"http://localhost:{settings.port}",
            f"127.0.0.1:{settings.port}",
            f"localhost:{settings.port}",
            f":{settings.port}",
        ))

    active = False
    if isinstance(payload, dict):
        web = payload.get("Web")
        allow = payload.get("AllowFunnel")
        allow_for_host = False
        if isinstance(allow, dict):
            allow_for_host = any(
                bool(value) and (not hostname or hostname in str(key))
                for key, value in allow.items()
            )
        elif isinstance(allow, bool):
            allow_for_host = allow

        # Dana owns the canonical public HTTPS endpoint on port 443. An old
        # Funnel on 8443 (or another service on 443) must not make the status look
        # healthy, otherwise the generated 443 URL can silently return 404.
        canonical = web.get(f"{hostname}:443") if isinstance(web, dict) and hostname else None
        if canonical:
            canonical_text = json.dumps(canonical, ensure_ascii=False).lower()
            active = contains_local_target(canonical) and (
                allow_for_host or f"{hostname}:443" in canonical_text or "https" in canonical_text
            )
        elif allow_for_host and hostname:
            # Do not infer Dana's health from an unrelated listener.
            active = False

    lowered = raw.lower()
    has_public_marker = "available on the internet" in lowered or "# funnel on:" in lowered
    canonical_raw = raw.split(f"https://{hostname}:8443", 1)[0] if hostname else raw
    if not active and result.returncode == 0 and hostname and has_public_marker and contains_local_target(canonical_raw):
        active = True

    if active:
        return True, hostname

    try:
        plain = _run(["tailscale", "funnel", "status"], timeout=10)
        text = (plain.stdout or "") + "\n" + (plain.stderr or "")
        plain_host = _find_funnel_hostname(text) or hostname
        plain_lower = text.lower()
        canonical_text = text.split(f"https://{plain_host}:8443", 1)[0] if plain_host else text
        plain_active = (
            plain.returncode == 0
            and bool(plain_host)
            and ("available on the internet" in plain_lower or "# funnel on:" in plain_lower)
            and contains_local_target(canonical_text)
        )
        return bool(plain_active), plain_host if plain_active else hostname
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
    active, funnel_host = _funnel_status() if installed else (False, "")
    public_host = funnel_host if active else ""
    token = settings.auth_token or ""
    token_path = f"/{token}/mcp" if token else "/mcp"
    local_url = f"http://127.0.0.1:{settings.port}{token_path}"
    public_url = f"https://{public_host}{token_path}" if public_host else ""
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
    with _AUTH_FLOW_LOCK:
        if _AUTH_FLOW["pending"] and _AUTH_FLOW["kind"] == "login" and backend.lower() == "running":
            _AUTH_FLOW.update(pending=False, auth_url="", message="")
            _setup_log("Tailscale browser authentication detected; continuing setup.", "success")
        elif _AUTH_FLOW["pending"] and _AUTH_FLOW["kind"] == "funnel" and active:
            _AUTH_FLOW.update(pending=False, auth_url="", message="")
            _setup_log("Tailscale Funnel approval detected; continuing setup.", "success")
    return SetupStatus(installed, backend, hostname, active, funnel_host, running, public_url or local_url, local_url, public_url, token, action, message)

def test_connections() -> dict[str, object]:
    import urllib.request

    checks: list[dict[str, object]] = []
    token = settings.require_auth_token()
    active, funnel_host = _funnel_status()
    candidates = [("local", f"http://127.0.0.1:{settings.port}/{token}{settings.mcp_path}", "127.0.0.1")]
    if active and funnel_host:
        candidates.append(("public", f"https://{funnel_host}/{token}{settings.mcp_path}", funnel_host))
    initialize = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "Dana Control Center", "version": "1.0"},
        },
    }).encode("utf-8")
    for name, url, host in candidates:
        try:
            request = urllib.request.Request(
                url,
                data=initialize,
                method="POST",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "Host": host,
                },
            )
            with urllib.request.urlopen(request, timeout=12) as response:
                raw = response.read(65536).decode("utf-8", "replace")
                content_type = response.headers.get("content-type", "")
                handshake_ok = response.status == 200 and (
                    "application/json" in content_type or "text/event-stream" in content_type
                )
                checks.append({
                    "name": name,
                    "url": url,
                    "ok": handshake_ok,
                    "status": response.status,
                    "content_type": content_type,
                    "handshake": "initialize" if handshake_ok else "failed",
                    "response_preview": raw[:240],
                })
        except Exception as exc:
            status_code = getattr(exc, "code", None)
            checks.append({
                "name": name,
                "url": url,
                "ok": False,
                "status": status_code,
                "handshake": "failed",
                "error": str(exc)[:180],
            })
    ok = bool(checks) and all(bool(item["ok"]) for item in checks)
    _setup_log("MCP initialize handshake passed." if ok else "MCP initialize handshake failed.", "success" if ok else "error")
    return {"ok": ok, "checks": checks, "tested_at": datetime.now(timezone.utc).isoformat()}


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


def _tailscale_static_arch() -> str:
    machine = platform.machine().lower()
    mapping = {
        "x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64",
        "armv7l": "arm", "armv6l": "arm", "i386": "386", "i686": "386",
        "mips": "mips", "mips64": "mips64", "mips64le": "mips64le", "mipsle": "mipsle",
        "riscv64": "riscv64", "geode": "geode",
    }
    try:
        return mapping[machine]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported Linux CPU architecture for Tailscale static binary: {machine}") from exc


def _static_tailscale_urls(arch: str) -> list[str]:
    """Discover the newest official static archive, then provide mirror fallbacks."""
    names: list[str] = []
    index_urls = [TAILSCALE_STATIC_OFFICIAL, TAILSCALE_STATIC_MIRROR]
    configured = os.getenv("DANA_TAILSCALE_MIRROR", "").strip().rstrip("/")
    if configured:
        index_urls.insert(0, configured + "/stable/static/")
    for index_url in index_urls:
        try:
            request = urllib.request.Request(index_url, headers={"User-Agent": "Dana-Setup/1"})
            with urllib.request.urlopen(request, timeout=15) as response:
                html = response.read().decode("utf-8", "replace")
            matches = re.findall(r"tailscale_(\d+(?:\.\d+)+)_" + re.escape(arch) + r"\.tgz", html)
            if matches:
                versions = sorted(set(matches), key=lambda v: tuple(int(x) for x in v.split(".")), reverse=True)
                version = versions[0]
                filename = f"tailscale_{version}_{arch}.tgz"
                base = index_url.rstrip("/") + "/"
                names.append(base + filename)
                names.append(TAILSCALE_STATIC_GITHUB + f"v{version}/" + filename)
                break
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError):
            continue
    return list(dict.fromkeys(names))


def _install_tailscale_static() -> dict[str, object]:
    arch = _tailscale_static_arch()
    urls = _static_tailscale_urls(arch)
    if not urls:
        raise RuntimeError("Could not discover a Tailscale static binary from the official package index or configured mirror.")
    target = Path(tempfile.gettempdir()) / f"tailscale-{arch}.tgz"
    last_error: Exception | None = None
    for url in urls:
        try:
            _setup_log(f"Trying Tailscale static binary source: {url}")
            _download_file(url, target, f"Tailscale static binary ({arch})")
            break
        except Exception as exc:
            last_error = exc
            _setup_log(f"Static binary source failed: {exc}", "warning")
    else:
        raise RuntimeError(f"All Tailscale static binary sources failed: {last_error}")

    extract_dir = Path(tempfile.mkdtemp(prefix="dana-tailscale-"))
    try:
        with tarfile.open(target, "r:gz") as archive:
            archive.extractall(extract_dir, filter="data")
        tailscale_bin = next(extract_dir.rglob("tailscale"), None)
        tailscaled_bin = next(extract_dir.rglob("tailscaled"), None)
        service = next(extract_dir.rglob("tailscaled.service"), None)
        if not tailscale_bin or not tailscaled_bin:
            raise RuntimeError("Tailscale static archive does not contain tailscale and tailscaled binaries.")
        result = _privileged_run(["install", "-Dm755", str(tailscale_bin), "/usr/bin/tailscale"], timeout=60)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Could not install /usr/bin/tailscale").strip())
        result = _privileged_run(["install", "-Dm755", str(tailscaled_bin), "/usr/sbin/tailscaled"], timeout=60)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Could not install /usr/sbin/tailscaled").strip())
        if service and command_exists("systemctl"):
            result = _privileged_run(["install", "-Dm644", str(service), "/usr/lib/systemd/system/tailscaled.service"], timeout=60)
            if result.returncode == 0:
                _privileged_run(["systemctl", "daemon-reload"], timeout=30)
                _privileged_run(["systemctl", "enable", "--now", "tailscaled"], timeout=45)
        if not command_exists("tailscale"):
            raise RuntimeError("Static Tailscale installation completed without a usable tailscale command.")
        _setup_log(f"Tailscale static binary installed successfully ({arch}).", "success")
        return {"ok": True, "installed": True, "message": f"Tailscale installed from static binary ({arch})."}
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def install_tailscale() -> dict[str, object]:
    _setup_log("Starting Tailscale installation.")
    if command_exists("tailscale"):
        _setup_log("Tailscale is already installed.")
        return {"ok": True, "installed": True, "message": "Tailscale is already installed."}
    system = platform.system().lower()
    if system == "linux":
        if not shutil.which("pkexec") and not shutil.which("sudo") and not (hasattr(os, "geteuid") and os.geteuid() == 0):
            return {"ok": False, "action_required": "manual_install", "message": "Administrator privileges are required. Install sudo or a desktop policy agent and retry.", "url": TAILSCALE_DOWNLOAD}
        try:
            target = Path(tempfile.gettempdir()) / "tailscale-install.sh"
            _download_file(TAILSCALE_INSTALL_SCRIPT, target, "Tailscale installer")
            _setup_log("Launching the privileged Tailscale installer; administrator authentication may be requested.")
            result = _privileged_run(["sh", str(target)], timeout=240)
            output = (result.stderr or result.stdout or "").strip()
            if result.returncode == 0 and command_exists("tailscale"):
                _setup_log("Tailscale installer completed successfully.", "success")
                return {"ok": True, "installed": True, "message": "Tailscale installation finished."}
            _setup_log(
                "Official Tailscale installer failed; switching to the static binary fallback"
                + (f": {output}" if output else "."),
                "warning",
            )
            try:
                return _install_tailscale_static()
            except Exception as static_exc:
                details = output or f"installer exited with code {result.returncode}"
                _setup_log(f"Tailscale static fallback failed: {static_exc}", "error")
                return {
                    "ok": False,
                    "message": f"Installer failed: {details}; static fallback failed: {static_exc}",
                    "url": TAILSCALE_DOWNLOAD,
                }
        except Exception as exc:
            _setup_log(f"Official Tailscale installer could not run: {exc}; trying static fallback.", "warning")
            try:
                return _install_tailscale_static()
            except Exception as static_exc:
                return {"ok": False, "message": f"{exc}; static fallback failed: {static_exc}", "url": TAILSCALE_DOWNLOAD}
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
        _download_file(win_url, target, "Tailscale Windows installer")
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
        _download_file(mac_url, target, "Tailscale macOS installer")
        subprocess.Popen(["open", str(target)])
        return {"ok": False, "pending": True, "message": "Tailscale installer opened. Complete the installation and return to Dana.", "url": TAILSCALE_DOWNLOAD}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "url": TAILSCALE_DOWNLOAD}

def login_tailscale() -> dict[str, object]:
    _setup_log("Checking Tailscale authentication.")
    if not command_exists("tailscale"):
        _setup_log("Cannot authenticate because Tailscale is not installed.", "error")
        return {"ok": False, "action_required": "install_tailscale", "message": "Install Tailscale first."}
    result = _privileged_run(["tailscale", "up"], timeout=45)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    auth_url = _find_auth_url(output)
    if auth_url:
        _set_auth_flow("login", auth_url, "Open the Tailscale login URL in your browser and complete authentication.", True)
        _setup_log("Tailscale requested browser authentication. Opening the login page.")
        _open(auth_url)
        return {"ok": True, "pending": True, "message": "Complete Tailscale authentication in the browser. Dana will continue automatically.", "auth_url": auth_url}
    if result.returncode == 0:
        _set_auth_flow()
        _setup_log("Tailscale authentication completed.", "success")
        return {"ok": True, "message": "Tailscale is connected."}
    details = output.strip() or f"tailscale up exited with code {result.returncode}"
    _setup_log("Tailscale authentication failed: " + details, "error")
    return {"ok": False, "message": details}

def enable_funnel(port: int = 8765) -> dict[str, object]:
    _setup_log("Starting Tailscale Funnel setup.")
    if not command_exists("tailscale"):
        _setup_log("Cannot enable Funnel because Tailscale is not installed.", "error")
        return {"ok": False, "action_required": "install_tailscale", "message": "Install Tailscale first."}
    try:
        _ensure_tailscale_ready()
    except RuntimeError as exc:
        details = str(exc)
        auth_url = _find_auth_url(details)
        if auth_url:
            _set_auth_flow("funnel", auth_url, "Open the Tailscale Funnel approval URL in your browser and approve it.", True)
            _setup_log("Tailscale requested Funnel approval in the browser. Opening the approval page.")
            _open(auth_url)
            return {"ok": True, "pending": True, "action_required": "enable_funnel", "message": "Approve Funnel in the browser. Dana will continue automatically.", "auth_url": auth_url}
        _setup_log("Tailscale is not ready for Funnel: " + details, "error")
        return {"ok": False, "action_required": "login_tailscale", "message": details}
    try:
        host = configure_tailscale_local(settings.auth_token, port=port, funnel_port=443)
    except RuntimeError as exc:
        details = str(exc)
        auth_url = _find_auth_url(details)
        if auth_url:
            _set_auth_flow("funnel", auth_url, "Open the Tailscale Funnel approval URL in your browser and approve it.", True)
            _setup_log("Tailscale requested Funnel approval in the browser. Opening the approval page.")
            _open(auth_url)
            return {"ok": True, "pending": True, "action_required": "enable_funnel", "message": "Approve Funnel in the browser. Dana will continue automatically.", "auth_url": auth_url}
        _setup_log("Funnel configuration failed: " + details, "error")
        return {"ok": False, "message": details}
    token = write_env("local", workers=settings.workers)
    settings.auth_token = token
    os.environ["DANA_AUTH_TOKEN"] = token
    set_local_public_host(host)
    active = False
    for _ in range(20):
        active, detected_host = _funnel_status()
        host = detected_host or host
        if active:
            break
        time.sleep(0.5)
    verified = verify_public_endpoint(host) if active else False
    if active:
        _setup_log(f"Funnel is active on {host}; endpoint verification: {'passed' if verified else 'pending'}.", "success")
        token_path = f"/{settings.auth_token}/mcp" if settings.auth_token else "/mcp"
        return {"ok": True, "hostname": host, "url": f"https://{host}{token_path}", "endpoint_verified": verified, "message": "Funnel is active and the MCP endpoint is ready." if verified else "Funnel is active; the MCP endpoint is warming up."}
    _setup_log(f"Funnel configuration was accepted but status is still pending for {host}.", "warning")
    token_path = f"/{settings.auth_token}/mcp" if settings.auth_token else "/mcp"
    return {"ok": True, "pending": True, "hostname": host, "url": f"https://{host}{token_path}", "endpoint_verified": False, "action_required": "enable_funnel", "message": "Funnel approval completed; waiting for Tailscale to publish the endpoint."}

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
    """Stop Dana and remove the desktop-owned Funnel route."""
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

    # Funnel was started with --bg, so it survives independently of Dana.
    # Remove only the HTTPS 443 route used by Dana.
    if command_exists("tailscale"):
        try:
            funnel_stop = _privileged_run(["tailscale", "funnel", "--https=443", "off"], timeout=15)
            if funnel_stop.returncode == 0:
                _setup_log("Dana Tailscale Funnel route stopped.", "success")
            elif _funnel_active():
                _setup_log("Dana Funnel is still active after the stop request.", "warning")
        except (OSError, subprocess.TimeoutExpired) as exc:
            _setup_log(f"Could not stop Dana Funnel: {exc}", "warning")

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
