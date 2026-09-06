from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time

from .config import settings


class DanaFunnelManager:
    """Own and rapidly restore Dana's token path without touching shared routes."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._log = logging.getLogger("dana")

    @property
    def enabled(self) -> bool:
        return (
            settings.normalized_mode() == "local"
            and settings.tailscale_funnel_enabled
            and shutil.which("tailscale") is not None
        )

    def _run(self, command: list[str]) -> bool:
        try:
            result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._log.warning("Dana Funnel command failed: %s", exc)
            return False
        if result.returncode:
            self._log.warning("Dana Funnel route restore failed: %s", (result.stderr or result.stdout).strip())
            return False
        return True

    def ensure(self, retries: int = 3) -> bool:
        """Restore only Dana's unique path; never reset or remove port 443."""
        if not self.enabled:
            return False
        token = settings.require_auth_token()
        backend = f"http://127.0.0.1:{settings.port}"
        command = ["tailscale", "funnel", "--https=443", "--set-path", f"/{token}", "--yes", "--bg", backend]
        for attempt in range(retries):
            if self._run(command):
                return True
            if attempt + 1 < retries:
                time.sleep(0.5)
        return False

    def start(self) -> None:
        if not self.enabled:
            return
        self.ensure()
        self._thread = threading.Thread(target=self._watch, name="dana-funnel-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _watch(self) -> None:
        interval = max(1, settings.tailscale_funnel_check_seconds)
        while not self._stop.wait(interval):
            # Restore Dana after another application's shutdown clears handlers.
            self.ensure(retries=1)
