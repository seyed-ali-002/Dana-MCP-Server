from __future__ import annotations

import logging
import shutil
import subprocess
import threading

from .config import settings


class DanaFunnelManager:
    """Keeps Dana's public Funnel route present independently of other apps."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return (
            settings.normalized_mode() == "local"
            and settings.tailscale_funnel_enabled
            and shutil.which("tailscale") is not None
        )

    def ensure(self) -> bool:
        if not self.enabled:
            return False
        settings.require_auth_token()
        command = [
            "tailscale",
            "funnel",
            "--https=443",
            "--set-path",
            "/",  # Dana public root; tokenized MCP path is handled by Dana middleware.
            "--yes",
            "--bg",
            f"http://127.0.0.1:{settings.port}",
        ]
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        if result.returncode:
            logging.getLogger("dana").warning(
                "Dana Funnel route check failed: %s",
                (result.stderr or result.stdout).strip(),
            )
            return False
        return True

    def start(self) -> None:
        if not self.enabled:
            return
        self.ensure()
        self._thread = threading.Thread(
            target=self._watch,
            name="dana-funnel-watchdog",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _watch(self) -> None:
        interval = max(5, settings.tailscale_funnel_check_seconds)
        while not self._stop.wait(interval):
            # Reconcile Dana's own public route so the root and MCP endpoint
            # remain available after unrelated applications stop.
            self.ensure()
