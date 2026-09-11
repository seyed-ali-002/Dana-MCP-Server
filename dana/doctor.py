from __future__ import annotations

import argparse
import importlib
import json
import platform
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .config import Settings

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PYTHON = ((3, 11), (3, 12), (3, 13))


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def _run(command: list[str], timeout: float = 8) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    raw = path.read_text(encoding="utf-8").replace("\\n", "\n")
    for line in raw.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("dana-mcp-server")
    except Exception:
        pyproject = ROOT / "pyproject.toml"
        for line in pyproject.read_text(encoding="utf-8").splitlines() if pyproject.exists() else []:
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')
        return "unknown"


def _git_commit() -> str:
    result = _run(["git", "rev-parse", "--short", "HEAD"])
    return result.stdout.strip() if result and result.returncode == 0 else "unavailable"


def _masked_token(token: str) -> str:
    if not token:
        return "missing"
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def connection_url(settings: Settings, show_url: bool = False) -> str:
    if not settings.public_host:
        return "public host is not configured"
    if settings.normalized_mode() == "server":
        return f"https://{settings.public_host}{settings.mcp_path}"
    authority = settings.public_host
    if settings.public_port and settings.public_port not in (80, 443):
        authority = f"{authority}:{settings.public_port}"
    token = settings.auth_token if show_url else _masked_token(settings.auth_token)
    return f"https://{authority}/{token}{settings.mcp_path}"


def _http_check(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, type(exc).__name__


def collect_checks(settings_factory: Callable[[], Settings] = Settings) -> tuple[list[Check], dict[str, str]]:
    checks: list[Check] = []
    info = {"dana_version": _version(), "git_commit": _git_commit(), "platform": f"{platform.system()} {platform.release()}", "python": platform.python_version()}
    py = sys.version_info[:2]
    if py in SUPPORTED_PYTHON:
        checks.append(Check("Python version", "PASS", f"Python {platform.python_version()} is tested"))
    elif py >= (3, 11):
        checks.append(Check("Python version", "WARN", f"Python {platform.python_version()} meets minimum requirements but is not in tested 3.11-3.13 range", "Use Python 3.12 or 3.13 and recreate .venv if this machine behaves differently."))
    else:
        checks.append(Check("Python version", "FAIL", f"Python {platform.python_version()} is unsupported", "Install Python 3.11-3.13, remove .venv, then rerun installer."))

    env_path = ROOT / ".env"
    checks.append(Check("Configuration file", "PASS" if env_path.exists() else "FAIL", str(env_path) if env_path.exists() else ".env is missing", "" if env_path.exists() else "Run the Dana installer."))

    try:
        settings = settings_factory()
        mode = settings.normalized_mode()
        workers = settings.normalized_workers()
        checks.append(Check("Dana configuration", "PASS" if settings.auth_token else "FAIL", f"mode={mode}, workers={workers}, token={_masked_token(settings.auth_token)}", "" if settings.auth_token else "Configure DANA_AUTH_TOKEN."))
    except Exception as exc:
        checks.append(Check("Dana configuration", "FAIL", str(exc), "Fix .env values and rerun Dana Doctor."))
        return checks, info

    required = [ROOT/"dana"/"http.py", ROOT/"dana"/"server.py", ROOT/"dana"/"tools"/"runtime_optimization.py"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    checks.append(Check("Required Dana files", "PASS" if not missing else "FAIL", "all required files present" if not missing else "missing: " + ", ".join(missing), "" if not missing else "Run git pull and reinstall dependencies; do not copy individual files between versions."))

    deps = ("fastapi", "uvicorn", "mcp", "pydantic_settings")
    broken = []
    for name in deps:
        try:
            importlib.import_module(name)
        except Exception:
            broken.append(name)
    checks.append(Check("Core dependencies", "PASS" if not broken else "FAIL", "all core dependencies import successfully" if not broken else "missing/broken: " + ", ".join(broken), "" if not broken else "Reinstall requirements inside Dana .venv."))

    listening = False
    try:
        with socket.create_connection((settings.host, settings.port), timeout=0.5):
            listening = True
    except OSError:
        pass
    checks.append(Check("Dana process", "PASS" if listening else "WARN", f"{settings.host}:{settings.port} is {'listening' if listening else 'not listening'}", "" if listening else "Start Dana, then run Doctor again to verify live routes."))

    if listening:
        ok, detail = _http_check(f"http://{settings.host}:{settings.port}/health")
        checks.append(Check("Health endpoint", "PASS" if ok else "FAIL", detail, "Inspect Dana logs if /health does not return HTTP 200."))
        ok, detail = _http_check(f"http://{settings.host}:{settings.port}/.well-known/oauth-protected-resource/mcp")
        checks.append(Check("OAuth discovery", "PASS" if ok else "FAIL", detail, "Verify dana/http.py and restart Dana after updating."))

    if settings.normalized_mode() == "local":
        tailscale = _run(["tailscale", "status", "--json"])
        if tailscale is None:
            checks.append(Check("Tailscale", "FAIL", "tailscale command is unavailable", "Install Tailscale, sign in, and ensure its CLI is in PATH."))
        elif tailscale.returncode != 0:
            checks.append(Check("Tailscale", "FAIL", (tailscale.stderr or tailscale.stdout).strip() or "not ready", "Open Tailscale, sign in, and confirm the device is connected."))
        else:
            try:
                state = json.loads(tailscale.stdout).get("BackendState", "unknown")
            except json.JSONDecodeError:
                state = "invalid JSON"
            checks.append(Check("Tailscale", "PASS" if str(state).lower() == "running" else "WARN", f"BackendState={state}", "" if str(state).lower() == "running" else "Reconnect Tailscale and wait for BackendState=Running."))

        funnel = _run(["tailscale", "funnel", "status"])
        if funnel and funnel.returncode == 0:
            detail = (funnel.stdout or funnel.stderr).strip()
            status = "PASS" if detail else "WARN"
            checks.append(
                Check(
                    "Tailscale Funnel",
                    status,
                    detail[:300] or "status returned no routes",
                    "" if detail else "Run installer or tailscale funnel --https=443 --yes --bg <DANA_PORT>.",
                )
            )
        else:
            detail = (funnel.stderr or funnel.stdout).strip()[:300] if funnel else "funnel command unavailable"
            checks.append(Check("Tailscale Funnel", "WARN", detail or "not configured", "Run installer and verify Funnel is enabled for this Tailnet."))

    checks.append(
        Check(
            "Connector URL",
            "PASS" if settings.public_host else "WARN",
            connection_url(settings),
            "" if settings.public_host else "Configure DANA_PUBLIC_HOST or rerun installer.",
        )
    )
    checks.append(Check("OAuth clients", "PASS", "ChatGPT/OpenAI, Claude/Anthropic, and Grok/xAI trusted HTTPS callback origins are supported"))
    return checks, info


def run_doctor(as_json: bool = False, show_url: bool = False) -> int:
    checks, info = collect_checks()
    settings = Settings()
    if as_json:
        payload = {"info": info, "checks": [asdict(check) for check in checks]}
        if show_url:
            payload["connection_url"] = connection_url(settings, True)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("DANA DOCTOR")
        print(f"Version: {info['dana_version']}  Commit: {info['git_commit']}")
        print(f"Platform: {info['platform']}  Python: {info['python']}")
        print()
        for check in checks:
            marker = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[check.status]
            print(f"{marker} [{check.status}] {check.name}: {check.detail}")
            if check.fix:
                print(f"  Fix: {check.fix}")
        if show_url:
            print(f"Connection URL: {connection_url(settings, True)}")
    return 1 if any(check.status == "FAIL" for check in checks) else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose Dana installation and connector issues.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--show-url", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_doctor(as_json=args.as_json, show_url=args.show_url))


if __name__ == "__main__":
    main()
