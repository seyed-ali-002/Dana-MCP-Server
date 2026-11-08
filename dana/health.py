"""Layered health checks for Dana LOCAL / PUBLIC / Funnel / MCP (R17-01)."""
from __future__ import annotations

import json
import os
import socket
import time
from typing import Any


def _tcp_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_local_mcp(port: int, token: str, mcp_path: str, timeout: float = 3.0) -> dict[str, Any]:
    """POST initialize against local MCP; returns ok + detail."""
    import urllib.error
    import urllib.request

    path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
    if token:
        url = f"http://127.0.0.1:{port}/{token}{path}"
    else:
        url = f"http://127.0.0.1:{port}{path}"
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "Dana-Health", "version": "1.7"},
            },
        }
    ).encode("utf-8")
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Host": "127.0.0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4096).decode("utf-8", "replace")
            ct = resp.headers.get("content-type", "")
            ok = resp.status == 200 and (
                "application/json" in ct or "text/event-stream" in ct or "jsonrpc" in raw
            )
            return {
                "ok": ok,
                "status": resp.status,
                "layer": "mcp_session",
                "detail": "Local MCP initialize OK" if ok else f"Unexpected response ({ct})",
                "url": url.split("?")[0],
            }
    except urllib.error.HTTPError as exc:
        # 401 still means the server is up and speaking MCP auth.
        code = int(getattr(exc, "code", 0) or 0)
        ok = code in {200, 401, 403}
        return {
            "ok": ok,
            "status": code,
            "layer": "mcp_session",
            "detail": f"HTTP {code}" + (" (auth-gated, transport up)" if ok else ""),
            "url": url.split("?")[0],
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "layer": "mcp_session",
            "detail": str(exc)[:200],
            "url": url.split("?")[0],
        }


def build_health_snapshot(
    *,
    port: int,
    token: str,
    mcp_path: str,
    dana_running: bool,
    funnel_active: bool,
    funnel_hostname: str,
    public_verified: bool,
    tailscale_backend: str,
    local_only: bool,
    user_stopped: bool,
    connectivity: str,
) -> dict[str, Any]:
    """Structured multi-layer health for UI/CLI/watchdog."""
    local_tcp = bool(dana_running) or _tcp_open("127.0.0.1", int(port))
    layers: dict[str, Any] = {
        "local": {
            "ok": local_tcp,
            "detail": f"TCP 127.0.0.1:{port} " + ("open" if local_tcp else "closed"),
        },
        "funnel": {
            "ok": bool(funnel_active) if not local_only else True,
            "detail": (
                "local-only mode"
                if local_only
                else (funnel_hostname or "inactive")
            ),
            "hostname": funnel_hostname or "",
        },
        "public": {
            "ok": bool(public_verified) if not local_only else True,
            "detail": (
                "skipped (local-only)"
                if local_only
                else ("HTTPS responds" if public_verified else "not verified")
            ),
        },
        "tailscale": {
            "ok": (tailscale_backend or "").lower() == "running" or local_only,
            "detail": tailscale_backend or "unknown",
        },
        "mcp_session": {
            "ok": False,
            "detail": "not probed",
        },
    }
    if local_tcp and token is not None:
        layers["mcp_session"] = probe_local_mcp(int(port), token or "", mcp_path or "/mcp")
    elif not local_tcp:
        layers["mcp_session"] = {
            "ok": False,
            "detail": "runtime not listening",
            "layer": "mcp_session",
        }

    overall = "connected"
    if user_stopped and not local_tcp:
        overall = "stopped"
    elif connectivity:
        overall = connectivity

    return {
        "ok": bool(layers["local"]["ok"]) and (
            local_only or bool(layers["funnel"]["ok"]) or not layers["tailscale"]["ok"]
        ),
        "overall": overall,
        "layers": layers,
        "user_stopped": bool(user_stopped),
        "local_only": bool(local_only),
        "checked_at": time.time(),
        "stateless_http": (os.getenv("DANA_STATELESS_HTTP") or "1").strip().lower()
        not in {"0", "false", "no", "off"},
        "hints": _hints(layers, local_only=local_only, user_stopped=user_stopped),
    }


def _hints(layers: dict[str, Any], *, local_only: bool, user_stopped: bool) -> list[str]:
    out: list[str] = []
    if user_stopped:
        out.append("Dana was stopped by the user; Start is required to run again.")
    if not layers.get("local", {}).get("ok"):
        out.append("Local MCP port is closed. Click Start / Activate.")
    elif not layers.get("mcp_session", {}).get("ok"):
        out.append("Port is open but MCP handshake failed. Check logs or Repair.")
    if not local_only and not layers.get("tailscale", {}).get("ok"):
        out.append("Tailscale is offline. Sign in; VPN may block 100.x routes.")
    if not local_only and layers.get("tailscale", {}).get("ok") and not layers.get("funnel", {}).get("ok"):
        out.append("Funnel is not published. Use Enable Funnel or Repair.")
    if not local_only and layers.get("funnel", {}).get("ok") and not layers.get("public", {}).get("ok"):
        out.append("Funnel is on but public HTTPS is not responding yet.")
    if not out:
        out.append("All checked layers look healthy.")
    return out


def friendly_setup_error(exc: BaseException | str) -> str:
    """Map low-level exceptions to short user-facing setup messages (R17-08)."""
    text = str(exc)
    low = text.lower()
    if "10053" in text or "connection was aborted" in low:
        return (
            "Connection closed by the host (WinError 10053). "
            "Stop Dana, wait a second, then Start again. Disable conflicting antivirus proxy if it persists."
        )
    if "charmap" in low or "codec can't encode" in low:
        return (
            "Console encoding error on this Windows locale. "
            "Update Dana; logs should use UTF-8. Restart the Control Center."
        )
    if "permission denied" in low or "errno 13" in low:
        return "Permission denied. Grant path access in Configuration or run the needed step with administrator rights."
    if "session not found" in low or "missing session" in low:
        return (
            "MCP session expired. Reconnect the client (new chat / reconnect connector). "
            "Dana uses stateless HTTP by default to reduce this."
        )
    if "certificate verify failed" in low or "ssl:" in low:
        return (
            "TLS certificate verification failed. Ensure system CA certificates are installed "
            "(or update certifi). Local MCP is unaffected."
        )
    if "address already in use" in low or "errno 98" in low or "10048" in text:
        return "Local port is busy. Dana will try the next free port, or stop the other process."
    if "timed out" in low or "timeout" in low:
        return "Operation timed out. Check network/Tailscale and try Repair connection."
    if len(text) > 280:
        return text[:277] + "…"
    return text
