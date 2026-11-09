"""MCP Super Assistant proxy bridge for Dana.

Runs @srbhptl39/mcp-superassistant-proxy against the local Dana Streamable HTTP
endpoint so browser extensions (Gemini, Perplexity, ChatGPT web, ...) can use Dana
without native MCP support.

Permission / path rules learned from SuperMCP deployments:
- Never write under system or read-only mount points; use ~/.config/dana/supermcp.
- Unset LD_LIBRARY_PATH for the Node child (AppImage / bundled lib conflicts).
- Prefer npx; fall back to a local SuperMCP install if present via DANA_SUPERMCP_HOME.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import settings
from .subprocess_env import clean_subprocess_env

_PROXY_PKG = "@srbhptl39/mcp-superassistant-proxy@0.1.8"
_DEFAULT_PORT = 3006
_PROCESS: subprocess.Popen[str] | None = None


def _data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif os.uname().sysname.lower() == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    path = base / "dana" / "supermcp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pid_file() -> Path:
    return _data_dir() / "proxy.pid"


def _config_file() -> Path:
    return _data_dir() / "config.json"


def _log_file() -> Path:
    return _data_dir() / "proxy.log"


def _manifest_file() -> Path:
    return _data_dir() / "dana-tools.json"


def generate_full_tool_manifest() -> Path:
    """Export every registered Dana tool into the SuperMCP data dir."""
    target = _manifest_file()
    try:
        from .server import mcp
        from .tools.tool_catalog import enrich

        manager = getattr(mcp, "_tool_manager", None)
        raw_tools: list = []
        if manager is not None:
            bucket = getattr(manager, "_tools", None)
            if isinstance(bucket, dict):
                raw_tools = sorted(bucket.values(), key=lambda tool: getattr(tool, "name", ""))
            elif hasattr(manager, "list_tools"):
                raw_tools = sorted(manager.list_tools(), key=lambda tool: getattr(tool, "name", ""))

        items: list = []
        for tool in raw_tools:
            try:
                items.append(enrich(tool))
            except Exception:
                items.append({
                    "name": getattr(tool, "name", "unknown"),
                    "canonical_name": getattr(tool, "name", "unknown"),
                    "category": "general",
                    "description": (getattr(tool, "description", "") or "").strip(),
                    "input_schema": getattr(tool, "parameters", {}) or {},
                })
        payload = {
            "count": len(items),
            "categories": sorted({str(x.get("category") or "general") for x in items}),
            "tools": items,
        }
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass
    return target



def _port() -> int:
    raw = os.environ.get("DANA_SUPERMCP_PORT", str(_DEFAULT_PORT))
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_PORT
    return value if 1 <= value <= 65535 else _DEFAULT_PORT


def _enabled_by_default() -> bool:
    raw = (os.environ.get("DANA_SUPERMCP_ENABLED") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _node_bin() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


def _npx_bin() -> str | None:
    return shutil.which("npx") or shutil.which("npx.cmd")


def _bundled_proxy_entry() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("DANA_SUPERMCP_HOME") or os.environ.get("SUPERMCP_HOME")
    if env:
        candidates.append(Path(env))
    for extra in (os.environ.get("DANA_SUPERMCP_EXTRA") or "").split(os.pathsep):
        if extra.strip():
            candidates.append(Path(extra.strip()))
    try:
        repo = Path(__file__).resolve().parents[1]
        candidates.append(repo.parent / "SuperMCP")
        candidates.append(repo / "SuperMCP")
    except Exception:
        pass
    for root in candidates:
        entry = root / "proxy" / "dist" / "index.js"
        if entry.is_file():
            return entry
    return None


def _auth_token() -> str:
    return (settings.auth_token or os.environ.get("DANA_AUTH_TOKEN") or "").strip()


def _dana_upstream_url() -> str:
    host = settings.host or "127.0.0.1"
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    port = int(settings.port or 8765)
    token = _auth_token()
    path = settings.mcp_path or "/mcp"
    if not path.startswith("/"):
        path = "/" + path
    if token:
        return f"http://{host}:{port}/{token}/mcp"
    return f"http://{host}:{port}{path}"


def write_config(*, tool_manifest: Path | None = None) -> Path:
    token = _auth_token()
    upstream = _dana_upstream_url()
    server: dict[str, Any] = {"url": upstream}
    if token:
        server["headers"] = {"Authorization": f"Bearer {token}"}
    if tool_manifest and tool_manifest.is_file():
        server["toolManifest"] = str(tool_manifest)
    else:
        try:
            generated = generate_full_tool_manifest()
            if generated.is_file():
                server["toolManifest"] = str(generated)
        except Exception:
            pass
    cached = _data_dir() / "dana-tools.json"
    if "toolManifest" not in server and cached.is_file():
        server["toolManifest"] = str(cached)
    for hist in (
        Path(os.environ.get("DANA_SUPERMCP_HOME") or "") / "dana-tools.json",
        Path(os.environ.get("SUPERMCP_HOME") or "") / "dana-tools.json",
        Path(__file__).resolve().parents[1] / "SuperMCP" / "dana-tools.json",
        Path(__file__).resolve().parents[1].parent / "SuperMCP" / "dana-tools.json",
    ):
        if "toolManifest" in server:
            break
        try:
            if hist.is_file():
                cached.write_text(hist.read_text(encoding="utf-8"), encoding="utf-8")
                server["toolManifest"] = str(cached)
                break
        except OSError:
            continue
    payload = {"mcpServers": {"Dana": server}}
    path = _config_file()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _read_pid() -> int | None:
    try:
        raw = _pid_file().read_text(encoding="utf-8").strip()
        pid = int(raw)
        return pid if pid > 0 else None
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _child_env() -> dict[str, str]:
    """Environment for Node/npx SuperMCP proxy without PyInstaller library leakage."""
    return clean_subprocess_env(extra={"DANA_SUPERMCP": "1"})


def _build_command(config_path: Path, port: int) -> list[str]:
    bundled = _bundled_proxy_entry()
    node = _node_bin()
    extra = ["--timeout", "120000", "--healthEndpoint", "/healthz"]
    if bundled is not None and node:
        return [
            node, str(bundled), "--config", str(config_path), "--port", str(port),
            "--outputTransport", "sse", "--cors", "--logLevel", "info", *extra,
        ]
    npx = _npx_bin()
    if npx:
        return [
            npx, "-y", _PROXY_PKG, "--config", str(config_path), "--port", str(port),
            "--outputTransport", "sse", "--cors", "--logLevel", "info", *extra,
        ]
    raise RuntimeError(
        "Node.js / npx is required for MCP Super Assistant proxy. "
        "Install Node 18+ or set DANA_SUPERMCP_HOME to a SuperMCP checkout."
    )


def status() -> dict[str, object]:
    port = _port()
    pid = _read_pid()
    alive = bool(pid and _pid_alive(pid))
    listening = _port_open(port)
    global _PROCESS
    if _PROCESS is not None and _PROCESS.poll() is not None:
        _PROCESS = None
    running = alive or listening or (_PROCESS is not None and _PROCESS.poll() is None)
    return {
        "enabled": _enabled_by_default(),
        "running": bool(running),
        "pid": pid if alive else None,
        "port": port,
        "sse_url": f"http://127.0.0.1:{port}/sse",
        "message_url": f"http://127.0.0.1:{port}/message",
        "config_path": str(_config_file()),
        "log_path": str(_log_file()),
        "upstream": _dana_upstream_url(),
        "node_available": bool(_node_bin() or _npx_bin()),
        "bundled_proxy": str(_bundled_proxy_entry() or ""),
    }


def start(*, port: int | None = None) -> dict[str, object]:
    global _PROCESS
    port = int(port or _port())
    current = status()
    if current.get("running") and current.get("port") == port:
        return {"ok": True, "message": "SuperMCP proxy already running.", **current}
    if not (_node_bin() or _npx_bin()):
        return {
            "ok": False,
            "message": "Node.js is not installed. Install Node 18+ to use MCP Super Assistant.",
            **status(),
        }
    try:
        config_path = write_config()
    except OSError as exc:
        return {
            "ok": False,
            "message": f"Cannot write SuperMCP config (permission?): {exc}. Expected writable dir {_data_dir()}.",
            **status(),
        }
    stale = _read_pid()
    if stale and not _pid_alive(stale):
        try:
            _pid_file().unlink(missing_ok=True)
        except OSError:
            pass
    if _port_open(port):
        return {"ok": True, "message": f"Port {port} already accepting connections (reusing).", **status()}
    try:
        cmd = _build_command(config_path, port)
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc), **status()}
    log = _log_file()
    try:
        log_handle = open(log, "a", encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "message": f"Cannot open SuperMCP log: {exc}", **status()}
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        log_handle.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} cmd={' '.join(cmd)} ---\n")
        log_handle.flush()
        _PROCESS = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=log_handle, stderr=subprocess.STDOUT,
            cwd=str(_data_dir()), env=_child_env(), creationflags=creationflags,
            start_new_session=(os.name != "nt"), text=True,
        )
    except OSError as exc:
        log_handle.close()
        msg = str(exc)
        if "Permission denied" in msg or getattr(exc, "errno", None) in {13, 1}:
            msg = (
                f"Permission denied starting SuperMCP proxy: {exc}. "
                f"Ensure Node is installed and {_data_dir()} is writable."
            )
        return {"ok": False, "message": msg, **status()}
    try:
        _pid_file().write_text(str(_PROCESS.pid), encoding="utf-8")
    except OSError:
        pass
    deadline = time.time() + 12
    while time.time() < deadline:
        if _PROCESS.poll() is not None:
            tail = ""
            try:
                tail = log.read_text(encoding="utf-8", errors="replace")[-800:]
            except OSError:
                pass
            return {"ok": False, "message": f"SuperMCP proxy exited early (code {_PROCESS.returncode}). {tail}", **status()}
        if _port_open(port):
            return {"ok": True, "message": f"SuperMCP proxy listening on http://127.0.0.1:{port}/sse", **status()}
        time.sleep(0.25)
    return {"ok": True, "message": "SuperMCP proxy started; waiting for port to open.", **status()}


def stop() -> dict[str, object]:
    global _PROCESS
    pid = _read_pid()
    stopped = False
    if _PROCESS is not None and _PROCESS.poll() is None:
        try:
            _PROCESS.terminate()
            try:
                _PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _PROCESS.kill()
            stopped = True
        except OSError:
            pass
        _PROCESS = None
    if pid and _pid_alive(pid):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True, env=clean_subprocess_env())
            else:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.4)
                if _pid_alive(pid):
                    os.kill(pid, signal.SIGKILL)
            stopped = True
        except OSError:
            pass
    try:
        _pid_file().unlink(missing_ok=True)
    except OSError:
        pass
    return {"ok": True, "message": "SuperMCP proxy stopped." if stopped else "SuperMCP proxy was not running.", **status()}


def restart(*, port: int | None = None) -> dict[str, object]:
    """Stop and start the SuperMCP proxy so upstream Dana sessions are fresh."""
    stop_result = stop()
    start_result = start(port=port)
    return {
        "ok": bool(start_result.get("ok")),
        "message": str(start_result.get("message") or "SuperMCP restarted"),
        "stopped": stop_result,
        **{k: v for k, v in start_result.items() if k not in {"ok", "message"}},
    }


def ensure_started() -> dict[str, object]:
    if not _enabled_by_default():
        return {"ok": True, "skipped": True, "message": "SuperMCP disabled (DANA_SUPERMCP_ENABLED).", **status()}
    return start()
