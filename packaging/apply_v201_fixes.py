#!/usr/bin/env python3
"""Apply post-2.0.1 functional + visual fixes."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_setup() -> None:
    path = ROOT / "dana" / "setup.py"
    t = path.read_text(encoding="utf-8")
    override = ROOT / "packaging" / "connection_mode_override.py"
    if override.exists() and "Could not persist connection mode" not in t:
        path.write_text(t.rstrip() + "\n" + override.read_text(encoding="utf-8"), encoding="utf-8")
        print("setup.py: appended connection mode override")
        t = path.read_text(encoding="utf-8")
    elif "Could not persist connection mode" in t:
        print("setup.py: connection mode already fixed")

    if 'connection_mode: str = "all"' not in t:
        t = t.replace(
            "    health: dict | None = None\n",
            '    health: dict | None = None\n    connection_mode: str = "all"\n',
            1,
        )
        path.write_text(t, encoding="utf-8")
        print("setup.py: added connection_mode field")
        t = path.read_text(encoding="utf-8")

    old_ret = """    return SetupStatus(
        installed, backend, hostname, active, funnel_host, running,
        public_url or local_url, local_url, public_url, token, action, message,
        connectivity, public_verified, hint, local_only, bool(_USER_STOPPED),
        _sm,
        health_snap,
    )"""
    new_ret = """    return SetupStatus(
        installed, backend, hostname, active, funnel_host, running,
        public_url or local_url, local_url, public_url, token, action, message,
        connectivity, public_verified, hint, local_only, bool(_USER_STOPPED),
        _sm,
        health_snap,
        get_connection_mode(),
    )"""
    if old_ret in t:
        path.write_text(t.replace(old_ret, new_ret, 1), encoding="utf-8")
        print("setup.py: status return includes connection_mode")


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


def patch_css() -> None:
    frag = ROOT / "packaging" / "css_post_2_0_polish.css"
    css_path = ROOT / "ui" / "src" / "App.css"
    if not frag.exists():
        print("css fragment missing")
        return
    body = css_path.read_text(encoding="utf-8")
    if "Post-2.0.0 layout & missing view polish" in body:
        print("css: already polished")
        return
    css_path.write_text(body.rstrip() + "\n" + frag.read_text(encoding="utf-8"), encoding="utf-8")
    print("css: polish appended")


def main() -> None:
    patch_setup()
    patch_app_version()
    patch_css()
    print("done")


if __name__ == "__main__":
    main()
