"""Graphical launcher for the Dana Desktop Control Center.

This module is the single owner of the ``dana gui`` execution path.
It prefers the packaged Tauri binary, falls back to the Tauri development
shell when sources and toolchains are available, then falls back to serving
the built web UI (``ui/dist``) over the local setup API, and finally falls
back to a console status view. It only uses the standard library so no
optional ``pip`` extra is required.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
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


def _ui_dist_ready() -> Path | None:
    dist = ROOT / "ui" / "dist"
    index = dist / "index.html"
    if index.is_file():
        return dist
    return None


def _launch_web_ui() -> bool:
    """Serve ``ui/dist`` + setup API and open the default browser.

    This keeps the install-to-run flow usable without Tauri/Rust toolchains
    when a production web build already exists.
    """
    dist = _ui_dist_ready()
    if dist is None:
        return False

    from . import setup_service

    api = setup_service.serve("127.0.0.1", 0)
    api_port = api.server_address[1]

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dist), **kwargs)

        def end_headers(self) -> None:
            # Allow the static UI (any origin on localhost) to call the setup API.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    static = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    static_port = static.server_address[1]
    threading.Thread(target=static.serve_forever, daemon=True, name="dana-ui-static").start()

    # Inject the setup API port into a tiny bootstrap so the SPA can find it
    # without Tauri's invoke("start_setup_service").
    bootstrap = dist / "dana-bootstrap.js"
    bootstrap.write_text(
        f"window.__DANA_SETUP_PORT__={api_port};\n",
        encoding="utf-8",
    )

    ui_url = f"http://127.0.0.1:{static_port}/?setupPort={api_port}"
    print(f"Dana Desktop (web): {ui_url}")
    print(f"Setup API: http://127.0.0.1:{api_port}/api/setup/status")
    # Brief delay so listeners are accepting before the browser hits them.
    time.sleep(0.35)
    webbrowser.open(ui_url)
    print("Press Ctrl+C to stop the Control Center.")
    try:
        api.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        static.shutdown()
        static.server_close()
        api.shutdown()
        api.server_close()
        try:
            bootstrap.unlink(missing_ok=True)
        except OSError:
            pass
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
    args = sys.argv[2:] if len(sys.argv) > 1 and sys.argv[1] in {"gui", "setup", "desktop", "-m"} else sys.argv[1:]
    # When invoked as ``python -m dana.gui`` argv starts with the module path.
    if args and args[0].endswith("dana.gui"):
        args = args[1:]
    force_tauri = "--tauri" in args or os.getenv("DANA_GUI_ENGINE", "").lower() == "tauri"
    force_native = "--native" in args
    force_web = "--web" in args

    if force_web:
        if not _launch_web_ui():
            raise RuntimeError(
                "Web UI was requested but ui/dist is missing. "
                "Run `cd ui && npm run build` first."
            )
        return

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

    if _launch_web_ui():
        return

    _launch_console_fallback()


if __name__ == "__main__":
    main()
