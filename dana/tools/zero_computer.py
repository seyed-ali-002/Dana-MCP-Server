"""Optional bridge + helper install for Zero Use Computer."""
from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
from dana.subprocess_env import clean_subprocess_env
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

REPO = "mhrsdev/zero-use-computer"


def _bin_dir() -> Path:
    path = Path.home() / ".config" / "dana" / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_binary() -> str | None:
    which = shutil.which("zero") or shutil.which("zero-use-computer")
    if which:
        return which
    for name in ("zero", "zero-use-computer", "zero.exe", "zero-use-computer.exe"):
        candidate = _bin_dir() / name
        if candidate.is_file():
            return str(candidate)
    return None


def _platform_asset_hints() -> list[str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    hints: list[str] = []
    if system == "windows":
        hints += ["windows", "win", ".exe", "msvc"]
    elif system == "darwin":
        hints += ["darwin", "macos", "mac", "apple"]
        if "arm" in machine or "aarch" in machine:
            hints += ["arm64", "aarch64"]
        else:
            hints += ["x86_64", "amd64"]
    else:
        hints += ["linux"]
        if "arm" in machine or "aarch" in machine:
            hints += ["arm64", "aarch64"]
        else:
            hints += ["x86_64", "amd64"]
    return hints


def zero_status() -> dict[str, Any]:
    binary = _resolve_binary()
    return {
        "ok": bool(binary),
        "installed": bool(binary),
        "path": binary or "",
        "bin_dir": str(_bin_dir()),
        "message": "Zero Use Computer is available." if binary else "Not installed. Use install_zero_computer or download from GitHub releases.",
    }


def install_zero_computer() -> dict[str, Any]:
    """Download the latest Zero Use Computer release asset matching this OS/CPU."""
    existing = _resolve_binary()
    if existing and Path(existing).is_file():
        return {"ok": True, "already": True, "path": existing, "message": "Already installed."}

    api = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(
        api,
        headers={
            "User-Agent": "Dana-Setup/1",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Could not query GitHub releases: {exc}. Open https://github.com/{REPO}/releases/latest",
        }

    assets = payload.get("assets") or []
    hints = _platform_asset_hints()
    scored: list[tuple[int, dict[str, Any]]] = []
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        score = sum(1 for h in hints if h in name)
        # Prefer archives / binaries over source
        if name.endswith((".tar.gz", ".tgz", ".zip", ".exe")) or "zero" in name:
            score += 1
        if score:
            scored.append((score, asset))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {
            "ok": False,
            "message": f"No matching release asset for {platform.system()} {platform.machine()}. See https://github.com/{REPO}/releases/latest",
            "tag": payload.get("tag_name"),
        }

    asset = scored[0][1]
    url = str(asset.get("browser_download_url") or "")
    name = str(asset.get("name") or "zero-asset")
    if not url:
        return {"ok": False, "message": "Release asset has no download URL."}

    dest_dir = _bin_dir()
    download_path = dest_dir / name
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Dana-Setup/1"})
        with urllib.request.urlopen(req, timeout=120) as response, open(download_path, "wb") as fh:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as exc:
        return {"ok": False, "message": f"Download failed: {exc}"}

    # If archive, extract common binary names; else chmod + rename
    binary_path: Path | None = None
    lower = name.lower()
    if lower.endswith((".tar.gz", ".tgz")):
        import tarfile

        with tarfile.open(download_path, "r:gz") as tar:
            tar.extractall(dest_dir)
        for candidate in dest_dir.rglob("*"):
            if candidate.is_file() and candidate.name.lower() in {"zero", "zero-use-computer"}:
                binary_path = candidate
                break
    elif lower.endswith(".zip"):
        import zipfile

        with zipfile.ZipFile(download_path, "r") as zf:
            zf.extractall(dest_dir)
        for candidate in dest_dir.rglob("*"):
            if candidate.is_file() and candidate.name.lower() in {"zero", "zero-use-computer", "zero.exe"}:
                binary_path = candidate
                break
    else:
        binary_path = download_path

    if binary_path is None:
        return {
            "ok": False,
            "message": f"Downloaded {name} but could not locate the zero binary inside the archive.",
            "path": str(download_path),
        }

    final = dest_dir / ("zero.exe" if os.name == "nt" else "zero")
    if binary_path.resolve() != final.resolve():
        try:
            if final.exists():
                final.unlink()
            shutil.copy2(binary_path, final)
        except OSError:
            final = binary_path
    try:
        final.chmod(final.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

    return {
        "ok": True,
        "path": str(final),
        "tag": payload.get("tag_name"),
        "asset": name,
        "message": f"Zero Use Computer installed to {final}",
    }


def register_zero_computer_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def zero_computer(command: str = "status", args: str = "") -> dict[str, Any]:
        """Call the optional Zero Use Computer CLI if installed (https://github.com/mhrsdev/zero-use-computer)."""
        binary = _resolve_binary()
        if not binary:
            return {
                "ok": False,
                "installed": False,
                "message": "Zero Use Computer is not installed. Call install_zero_computer or use desktop_control.",
            }
        cmd = [binary]
        if command and command != "status":
            cmd.append(command)
        if args.strip():
            cmd.extend(args.split())
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=clean_subprocess_env())
        except Exception as exc:
            return {"ok": False, "installed": True, "error": str(exc)}
        return {
            "ok": result.returncode == 0,
            "installed": True,
            "path": binary,
            "returncode": result.returncode,
            "stdout": (result.stdout or "")[:20000],
            "stderr": (result.stderr or "")[:4000],
        }

    @mcp.tool()
    def install_zero_computer_tool() -> dict[str, Any]:
        """Download the latest Zero Use Computer binary for this platform into ~/.config/dana/bin."""
        return install_zero_computer()

    @mcp.tool()
    def zero_computer_status() -> dict[str, Any]:
        """Report whether Zero Use Computer is installed and where."""
        return zero_status()
