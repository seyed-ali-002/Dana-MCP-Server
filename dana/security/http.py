from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import socket
import time
from pathlib import Path
from collections import defaultdict, deque
from threading import Lock
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse


class SecurityError(PermissionError):
    pass


class RequestGuard:
    """Small dependency-free guard for authentication, rate limiting and SSRF checks."""

    def __init__(self, requests_per_minute: int = 120, auth_burst: int = 20) -> None:
        self.requests_per_minute = max(1, requests_per_minute)
        self.auth_burst = max(1, auth_burst)
        self._lock = Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._auth_failures: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def client_key(request: Request) -> str:
        # Dana's public backend is loopback-only. A proxy therefore becomes the
        # immediate peer and X-Forwarded-For is the useful client identity.
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()[:128]
        return (request.client.host if request.client else "unknown")[:128]

    def allow_request(self, key: str) -> bool:
        now = time.monotonic()
        window = 60.0
        with self._lock:
            bucket = self._requests[key]
            while bucket and now - bucket[0] >= window:
                bucket.popleft()
            if len(bucket) >= self.requests_per_minute:
                return False
            bucket.append(now)
            return True

    def allow_auth_attempt(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._auth_failures[key]
            while bucket and now - bucket[0] >= 60.0:
                bucket.popleft()
            if len(bucket) >= self.auth_burst:
                return False
            bucket.append(now)
            return True

    @staticmethod
    def token_matches(candidate: str, expected: str) -> bool:
        if not candidate or not expected:
            return False
        return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))

    @staticmethod
    def public_url_is_safe(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise SecurityError("Only HTTP(S) URLs with a hostname are allowed.")
        host = parsed.hostname
        if host.lower() in {"localhost", "localhost.localdomain"}:
            raise SecurityError("Localhost URLs are blocked.")
        try:
            addresses = {info[4][0] for info in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise SecurityError("The target hostname could not be resolved safely.") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise SecurityError("Requests to private or local network addresses are blocked.")


def unauthorized() -> JSONResponse:
    return JSONResponse(
        {"error": "Unauthorized"},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )



_AUDIT_FILE = Path(os.getenv("DANA_SECURITY_AUDIT_FILE", ".dana/security.log"))
_AUDIT_LOCK = Lock()


def audit(event: str, client: str, detail: str = "") -> None:
    """Append a privacy-preserving security event; never record bearer tokens."""
    digest = hashlib.sha256(client.encode("utf-8", "ignore")).hexdigest()[:16]
    record = {"time": time.time(), "event": event, "client": digest, "detail": detail[:200]}
    try:
        with _AUDIT_LOCK:
            _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _AUDIT_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if os.name != "nt":
                os.chmod(_AUDIT_FILE, 0o600)
    except OSError:
        # Security telemetry must never make the MCP operation fail.
        pass
