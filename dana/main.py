from __future__ import annotations

import logging
import os
import socket
from pathlib import Path
import uvicorn

from .config import settings
from .terminal_ui import server_dashboard

def _mode() -> str:
    return settings.normalized_mode()

def _public_url() -> str | None:
    if not settings.public_host:
        return None
    if _mode() == "server":
        return f"https://{settings.public_host}{settings.mcp_path}"
    authority = settings.public_host
    if settings.public_port:
        authority = f"{authority}:{settings.public_port}"
    return f"https://{authority}/{settings.require_auth_token()}{settings.mcp_path}"

PID_FILE = Path(__file__).resolve().parents[1] / ".dana.pid"

def _write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

def _remove_pid() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass

def run() -> None:
    mode = _mode()
    public_url = _public_url()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((settings.host, settings.port))
        probe.close()
    except OSError as exc:
        from .terminal_ui import startup_error
        startup_error(f"Port {settings.port} is already in use. Dana may already be running. Use ./stop to stop it.")
        return
    server_dashboard(settings, mode, public_url)

    # Worker names are deterministic and derived from DANA_AUTH_TOKEN.

    # Keep routine HTTP/session/access logging out of the terminal. Real server
    # errors remain available at ERROR level.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "mcp", "mcp.server", "mcp.server.streamable_http"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.ERROR)
    config = uvicorn.Config(
        "dana.http:app",
        host=settings.host,
        port=settings.port,
        log_level="error",
        access_log=False,
        reload=False,
        workers=settings.normalized_workers(),
    )
    _write_pid()
    try:
        uvicorn.Server(config).run()
    finally:
        _remove_pid()

if __name__ == "__main__":
    run()
