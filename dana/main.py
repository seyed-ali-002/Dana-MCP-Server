from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import uvicorn

from .config import settings
from .file_logging import configure_file_logging, install_terminal_mirror
from .terminal_ui import server_dashboard
from .tailscale import DanaFunnelManager


def _mode() -> str:
    return settings.normalized_mode()


def _public_url() -> str | None:
    if not settings.public_host:
        return None
    authority = settings.public_host
    if settings.public_port and settings.public_port not in (80, 443):
        authority = f"{authority}:{settings.public_port}"
    if _mode() == "server":
        return f"https://{authority}{settings.mcp_path}"
    # Stable Local Mode connection contract: the terminal always exposes the
    # tokenized MCP URL as https://<host>/<token>/mcp. Keep this format stable
    # across Dana releases; the durable token itself is read from persistent config.
    token = settings.require_auth_token()
    return f"https://{authority}/{token}{settings.mcp_path}"


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



def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_runtime_lock() -> None:
    """Ensure only one Dana MCP runtime serves the configured port."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", int(settings.port)), timeout=0.4):
            raise SystemExit(
                f"Dana is already running on port {settings.port}. "
                "Use the existing instance (or stop it first)."
            )
    except OSError:
        pass
    if PID_FILE.exists():
        try:
            old = int(PID_FILE.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            old = 0
        if old and old != os.getpid() and _pid_alive(old):
            raise SystemExit(
                f"Dana process {old} is already running. Stop it before starting another instance."
            )


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
    configure_file_logging()
    install_terminal_mirror()
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
    _acquire_runtime_lock()
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
