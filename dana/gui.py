"""Graphical launcher for the Dana Desktop Control Center.

This module is the single owner of the ``dana gui`` execution path.
It prefers the packaged Tauri binary, falls back to the Tauri development
shell when sources and toolchains are available, and finally falls back to
a browser opened on the locally built web UI (``ui/dist``) served together
with the setup API. It only uses the standard library so no optional
``pip`` extra is required.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_packaged_binary() -> Path | None:
    """Return the packaged Dana Desktop binary when it exists."""
    candidates = [
        ROOT / "ui" / "src-tauri" / "target" / "release" / ("Dana.exe" if os.name == "nt" else "Dana"),
        ROOT / "ui" / "src-tauri" / "target" / "release" / "bundle" / "appimage" / "Dana.AppImage",
    ]
    if sys.platform == "darwin":
        candidates.insert(
            0,
            ROOT / "ui" / "src-tauri" / "target" / "release" / "bundle" / "macos" / "Dana.app",
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _launch_packaged(binary: Path) -> None:
    if binary.suffix == ".app":
        subprocess.Popen(["open", str(binary)])
    else:
        subprocess.Popen([str(binary)], cwd=ROOT)
    print(f"Dana Desktop launched: {binary}")


def _launch_tauri_dev() -> bool:
    """Run the Tauri development shell. Returns True when launched."""
    ui = ROOT / "ui"
    if not ui.is_dir():
        return False
    if shutil.which("npm") is None:
        return False
    # ``cargo`` is only required for the native shell; ``--native`` forces the
    # web-only fallback below.
    if "--native" not in sys.argv[2:] and shutil.which("cargo") is None:
        return False
    subprocess.run(["npm", "run", "tauri", "dev"], cwd=ui, check=True)
    return True


def _launch_console_fallback() -> None:
    """Keep the install-to-run flow usable without Tauri toolchains.

    Starts the local setup API in the foreground and prints the endpoints
    the Desktop UI would show, so ``dana gui`` never fails silently on
    machines without Node.js/Rust or a packaged binary.
    """
    from . import setup
    from . import setup_service

    server = setup_service.serve("127.0.0.1", 0)
    port = server.server_address[1]
    print("Dana Desktop is not built in this checkout.")
    print("Build it with the Tauri pipeline in packaging/ or install the Dana Desktop package.")
    print(f"Local setup API: http://127.0.0.1:{port}/api/setup/status")
    try:
        current = setup.status().to_dict()
        print(f"Dana running: {current.get('dana_running')}")
        print(f"Local MCP: {current.get('local_mcp_url') or 'not ready'}")
        print(f"Public MCP: {current.get('public_mcp_url') or 'not ready'}")
    except Exception as exc:
        print(f"Could not read Dana status: {exc}")
    print("Press Ctrl+C to stop the setup API.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    """Entry point for ``dana gui`` and the ``dana-gui`` console script."""
    args = sys.argv[2:]
    force_tauri = "--tauri" in args or os.getenv("DANA_GUI_ENGINE", "").lower() == "tauri"
    force_native = "--native" in args

    binary = find_packaged_binary()
    if binary is not None and not force_tauri:
        _launch_packaged(binary)
        return

    if not force_native and _launch_tauri_dev():
        return

    if force_tauri:
        raise RuntimeError(
            "Tauri development shell was requested but is unavailable "
            "(missing UI sources, Node.js/npm or the Rust toolchain)."
        )
    _launch_console_fallback()


if __name__ == "__main__":
    main()
