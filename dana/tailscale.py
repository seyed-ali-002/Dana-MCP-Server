from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time

from .config import settings


class DanaFunnelManager:
    """Own and rapidly restore Dana public Funnel route after network flaps."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._log = logging.getLogger("dana")
        self._failures = 0

    @property
    def enabled(self) -> bool:
        try:
            from .installer import command_exists
            has_tailscale = command_exists("tailscale")
        except Exception:
            has_tailscale = shutil.which("tailscale") is not None
        return (
            settings.normalized_mode() == "local"
            and settings.tailscale_funnel_enabled
            and has_tailscale
        )

    def _ts_cmd(self, *args: str) -> list[str]:
        try:
            from .installer import _tailscale_cmd
            return _tailscale_cmd(*args)
        except Exception:
            return ["tailscale", *args]

    def _run(self, command: list[str]) -> bool:
        try:
            if command and command[0] == "tailscale":
                command = self._ts_cmd(*command[1:])
        except Exception:
            pass
        attempts: list[list[str]] = [list(command)]
        import os
        if (
            len(command) >= 2
            and "funnel" in command
            and hasattr(os, "geteuid")
            and os.geteuid() != 0
            and shutil.which("sudo")
        ):
            attempts.append(["sudo", "-n", *command])
        last_err = ""
        for cmd in attempts:
            try:
                result = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as exc:
                last_err = str(exc)
                continue
            if result.returncode == 0:
                return True
            last_err = (result.stderr or result.stdout or "").strip()
        if last_err:
            self._log.warning("Dana Funnel route restore failed: %s", last_err[:300])
        return False

    def _funnel_active(self) -> bool:
        try:
            result = subprocess.run(
                self._ts_cmd("funnel", "status"),
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        text = ((result.stdout or "") + chr(10) + (result.stderr or "")).lower()
        if result.returncode != 0:
            return False
        markers = (
            "available on the internet",
            "# funnel on:",
            f":{settings.port}",
            "https://",
            ".ts.net",
        )
        return any(m in text for m in markers)

    def _tailscale_online(self) -> bool:
        try:
            result = subprocess.run(
                self._ts_cmd("status", "--json"),
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode != 0:
            return False
        try:
            import json
            payload = json.loads(result.stdout or "{}")
        except Exception:
            return "running" in (result.stdout or "").lower()
        return str(payload.get("BackendState", "")).lower() == "running"

    def ensure(self, retries: int = 3) -> bool:
        if not self.enabled:
            return False
        if not self._tailscale_online():
            self._log.warning("Tailscale is offline; delaying Funnel restore until backend is Running.")
            return False
        if self._funnel_active():
            self._failures = 0
            return True
        command = ["tailscale", "funnel", "--https=443", "--yes", "--bg", str(settings.port)]
        for attempt in range(retries):
            if self._run(command):
                time.sleep(0.4)
                if self._funnel_active():
                    self._failures = 0
                    self._log.info("Dana Funnel route is active on port %s.", settings.port)
                    return True
            if attempt + 1 < retries:
                time.sleep(0.6)
        self._failures += 1
        return False

    def start(self) -> None:
        if not self.enabled:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._watch, name="dana-funnel-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _watch(self) -> None:
        base_interval = max(1, int(settings.tailscale_funnel_check_seconds))
        if not self._stop.wait(min(2.0, base_interval)):
            self.ensure(retries=3)
        while not self._stop.is_set():
            interval = 1 if self._failures else base_interval
            if self._stop.wait(interval):
                break
            self.ensure(retries=2 if self._failures else 1)

