from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import uvicorn

from .config import settings
from .terminal_ui import server_dashboard
from .tailscale import DanaFunnelManager


def _mode() -> str:
    return settings.normalized_mode()


def _public_url() -> str | None:
    if not settings.public_host:
        return None
    if _mode() == "server":
        return f"https://{settings.public_host}{settings.mcp_path}"
    authority = settings.public_host
    if settings.public_port and settings.public_port not in (80, 443):
        authority = f"{authority}:{settings.public_port}"
    return f"https://{authority}/{settings.require_auth_token()}{settings.mcp_path}"


def _runtime_dir() -> Path:
    configured = os.getenv("DANA_RUNTIME_DIR", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend([
        Path.home() / ".cache" / "dana",
        Path(tempfile.gettempdir()) / f"dana-{os.getuid() if hasattr(os, "getuid") else "user"}",
    ])
    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            test = directory / ".write-test"
            test.write_text("", encoding="utf-8")
            test.unlink(missing_ok=True)
            return directory
        except OSError:
            continue
    raise RuntimeError("Dana cannot create a writable runtime directory.")


PID_FILE = _runtime_dir() / "dana.pid"


def _write_pid() -> None:
    temp = PID_FILE.with_suffix(".tmp")
    temp.write_text(str(os.getpid()), encoding="utf-8")
    temp.replace(PID_FILE)


def _remove_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def run() -> None:
    mode = _mode()
    public_url = _public_url()
    server_dashboard(settings, mode, public_url)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "mcp", "mcp.server"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.handlers.clear()
        logger.propagate = False

    config = uvicorn.Config(
        "dana.http:app",
        host=settings.host,
        port=settings.port,
        log_level="error",
        access_log=False,
        reload=False,
        # Streamable HTTP sessions live in the MCP transport process. Multiple
        # Uvicorn processes would randomly route follow-up requests to a process
        # that does not own the session, producing "Missing session ID" / session
        # terminated errors. Keep one public transport process until a shared
        # session backend is explicitly configured.
        workers=1,
    )
    _write_pid()
    funnel = DanaFunnelManager()
    try:
        funnel.start()
        uvicorn.Server(config).run()
    finally:
        funnel.stop()
        _remove_pid()


if __name__ == "__main__":
    run()
