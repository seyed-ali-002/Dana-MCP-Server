from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from .subprocess_env import clean_subprocess_env
from pathlib import Path

_PLACEHOLDER_SUFFIXES = (
    "example.ts.net",
    "example.com",
    "localhost",
    "invalid",
)
_LOOPBACK = {"127.0.0.1", "::1", "0.0.0.0", "localhost"}
_TS_HOST_RE = re.compile(
    r"\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.ts\.net)\b",
    re.IGNORECASE,
)


def is_valid_public_host(host: str | None) -> bool:
    """True when host is safe to advertise as a public MCP endpoint."""
    if not host:
        return False
    h = str(host).strip().lower().rstrip(".")
    if not h or h in _LOOPBACK:
        return False
    if any(h == s or h.endswith("." + s) or h.endswith(s) for s in _PLACEHOLDER_SUFFIXES):
        return False
    if h.startswith("dana.example"):
        return False
    if "." not in h and ":" not in h:
        return False
    return True


def _tailscale_bin() -> str | None:
    try:
        from .installer import _tailscale_binary
        b = _tailscale_binary()
        if b:
            return str(b)
    except Exception:
        pass
    return shutil.which("tailscale")


def _run_ts(*args: str, timeout: float = 8.0) -> str:
    binary = _tailscale_bin()
    if not binary:
        return ""
    try:
        r = subprocess.run(
            [binary, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=clean_subprocess_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (r.stdout or "") + "\n" + (r.stderr or "")


def _from_funnel_status() -> str:
    raw = _run_ts("funnel", "status", "--json")
    if not raw.strip():
        raw = _run_ts("funnel", "status")
    payload = None
    try:
        stripped = raw.lstrip()
        if stripped.startswith("{"):
            payload = json.loads(stripped.splitlines()[0] if "\n" in stripped else stripped)
        else:
            payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None

    def walk(obj: object) -> str:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str):
                    m = _TS_HOST_RE.search(k)
                    if m:
                        return m.group(1).lower().rstrip(".")
                found = walk(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found:
                    return found
        elif isinstance(obj, str):
            m = _TS_HOST_RE.search(obj)
            if m:
                return m.group(1).lower().rstrip(".")
        return ""

    if payload is not None:
        found = walk(payload)
        if found:
            return found
    m = _TS_HOST_RE.search(raw)
    return m.group(1).lower().rstrip(".") if m else ""


def _from_tailscale_status() -> str:
    raw = _run_ts("status", "--json")
    if not raw.strip():
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        m = _TS_HOST_RE.search(raw)
        return m.group(1).lower().rstrip(".") if m else ""
    self_node = payload.get("Self") if isinstance(payload, dict) else None
    if isinstance(self_node, dict):
        dns = str(self_node.get("DNSName") or "").strip().rstrip(".").lower()
        if is_valid_public_host(dns):
            return dns
    m = _TS_HOST_RE.search(raw)
    return m.group(1).lower().rstrip(".") if m else ""


def _from_env_files() -> str:
    paths: list[Path] = []
    if os.name == "nt" and os.environ.get("APPDATA"):
        paths.append(Path(os.environ["APPDATA"]) / "dana" / ".env")
    else:
        paths.append(Path.home() / ".config" / "dana" / ".env")
    try:
        paths.append(Path(__file__).resolve().parents[1] / ".env")
    except Exception:
        pass
    for path in paths:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DANA_PUBLIC_HOST="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if is_valid_public_host(val):
                        return val.strip().rstrip(".")
        except OSError:
            continue
    env = os.environ.get("DANA_PUBLIC_HOST", "").strip()
    if is_valid_public_host(env):
        return env.rstrip(".")
    return ""


def resolve_public_host(preferred: str | None = None) -> str:
    """Resolve the hostname Dana should advertise on every platform.

    Never returns placeholder hosts like dana.example.ts.net.
    Live Funnel / Tailscale DNS wins over invalid preferred values.
    """
    pref = (preferred or "").strip().rstrip(".")
    ordered: list[str] = []
    if is_valid_public_host(pref):
        ordered.append(pref)

    live = _from_funnel_status() or _from_tailscale_status()
    if live and live not in ordered:
        if is_valid_public_host(pref):
            ordered.append(live)
        else:
            ordered.insert(0, live)

    for c in (_from_env_files(),):
        if c and c not in ordered:
            ordered.append(c)

    for host in ordered:
        if is_valid_public_host(host):
            return host.lower().rstrip(".")
    return ""


def ensure_settings_public_host() -> str:
    """Mutate module settings + env so advertisers always see a real host."""
    try:
        from .config import settings
    except Exception:
        return resolve_public_host()
    host = resolve_public_host(getattr(settings, "public_host", "") or "")
    if host:
        try:
            settings.public_host = host
        except Exception:
            pass
        os.environ["DANA_PUBLIC_HOST"] = host
        try:
            from .installer import set_local_public_host
            set_local_public_host(host)
        except Exception:
            pass
    return host
