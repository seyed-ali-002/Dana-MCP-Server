#!/usr/bin/env python3
"""Apply post-2.0.1 functional + visual fixes."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_setup() -> None:
    path = ROOT / "dana" / "setup.py"
    t = path.read_text(encoding="utf-8")
    if "Could not persist connection mode" in t and "env_vals = _read_env()" in t:
        print("setup.py: already patched")
        return

    pattern = re.compile(
        r"def get_connection_mode\(\)[\s\S]*?"
        r'return \{\n        "ok": True,\n        "connection_mode": m,\n'
        r'        "message": f"Connection mode switched to \{m\.upper\(\)\}\.",\n'
        r'        "status": status\(\)\.to_dict\(\),\n    \}'
    )
    replacement = '''def get_connection_mode() -> str:
    global _CONNECTION_MODE
    try:
        env_vals = _read_env()
    except Exception:
        env_vals = {}
    saved = str(
        env_vals.get("DANA_CONNECTION_MODE")
        or os.environ.get("DANA_CONNECTION_MODE")
        or _CONNECTION_MODE
        or "all"
    ).strip().lower()
    if saved in {"all", "local", "public", "supermcp"}:
        _CONNECTION_MODE = saved
        return saved
    return "all"


def set_connection_mode(mode: str = "all") -> dict[str, object]:
    """Switch Dana connection mode: all | local | public | supermcp."""
    global _CONNECTION_MODE
    m = (mode or "all").strip().lower()
    if m not in {"all", "local", "public", "supermcp"}:
        m = "all"
    _CONNECTION_MODE = m
    os.environ["DANA_CONNECTION_MODE"] = m
    try:
        env = _read_env()
        env["DANA_CONNECTION_MODE"] = m
        _write_env(env)
    except Exception as exc:
        _setup_log(f"Could not persist connection mode: {exc}", "warning")
    try:
        from . import supermcp
        if m == "local":
            set_local_only(True)
            try:
                supermcp.stop()
            except Exception:
                pass
            _setup_log("Connection mode set to Local Only (MCP :8765).", "info")
        elif m == "public":
            set_local_only(False)
            try:
                supermcp.stop()
            except Exception:
                pass
            _setup_log("Connection mode set to Public Funnel Only (MCP + HTTPS Funnel).", "info")
        elif m == "supermcp":
            set_local_only(True)
            try:
                supermcp.start()
            except Exception as sm_exc:
                _setup_log(f"SuperMCP start warning: {sm_exc}", "warning")
            _setup_log("Connection mode set to SuperMCP Assistant Only (MCP + SSE :3006).", "info")
        else:
            set_local_only(False)
            try:
                supermcp.start()
            except Exception as sm_exc:
                _setup_log(f"SuperMCP start warning: {sm_exc}", "warning")
            _setup_log("Connection mode set to All Services (Local + Public Funnel + SuperMCP).", "success")
    except Exception as exc:
        _setup_log(f"Connection mode switch warning: {exc}", "warning")
    st = status().to_dict()
    st["connection_mode"] = m
    return {
        "ok": True,
        "connection_mode": m,
        "message": f"Connection mode switched to {m.upper()}.",
        "status": st,
    }'''
    t2, n = pattern.subn(replacement, t, count=1)
    if n == 0:
        print("setup.py: pattern not found")
    else:
        path.write_text(t2, encoding="utf-8")
        print("setup.py: connection mode fixed")

    t = path.read_text(encoding="utf-8")
    if 'connection_mode: str = "all"' not in t:
        t = t.replace(
            "    health: dict | None = None\n",
            '    health: dict | None = None\n    connection_mode: str = "all"\n',
            1,
        )
        path.write_text(t, encoding="utf-8")
        print("setup.py: added connection_mode field")


def patch_app_version() -> None:
    path = ROOT / "ui" / "src" / "App.tsx"
    t = path.read_text(encoding="utf-8")
    t2 = re.sub(
        r'(typeof __APP_VERSION__ !== "undefined" \? __APP_VERSION__ : ")[^"]+(")',
        r"\g<1>2.0.1\2",
        t,
        count=1,
    )
    if t2 != t:
        path.write_text(t2, encoding="utf-8")
        print("App.tsx: version fallback -> 2.0.1")
    else:
        print("App.tsx: version already ok")


def main() -> None:
    patch_setup()
    patch_app_version()
    print("done")


if __name__ == "__main__":
    main()
