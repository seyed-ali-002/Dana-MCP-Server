from __future__ import annotations

import logging
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

def run() -> None:
    mode = _mode()
    public_url = _public_url()
    server_dashboard(settings, mode, public_url)
    # Keep terminal output focused on Dana's dashboard and real errors only.
    for name in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).setLevel(logging.WARNING)
    config = uvicorn.Config(
        "dana.http:app",
        host=settings.host,
        port=settings.port,
        log_level="warning",
        access_log=False,
        reload=False,
        workers=settings.normalized_workers(),
    )
    uvicorn.Server(config).run()

if __name__ == "__main__":
    run()
