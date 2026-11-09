"""Clean environment helper for child processes spawned by Dana.

When Dana runs from a PyInstaller bundle (Linux AppImage/deb, macOS .app, Windows .exe),
PyInstaller injects LD_LIBRARY_PATH / DYLD_LIBRARY_PATH / PYTHONHOME / PYTHONPATH pointing
to its temporary extraction directory (_MEIxxxxxx). Passing those variables to system
commands (git, curl, python3, node, npx, tailscale, etc.) breaks system shared libraries
(e.g. OpenSSL conflicts). This helper restores the original environment safely across
Linux, macOS, and Windows.
"""
from __future__ import annotations

import os


def clean_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for key in (
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
    ):
        orig_key = f"{key}_ORIG"
        if orig_key in env:
            env[key] = env[orig_key]
        else:
            env.pop(key, None)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    if extra:
        env.update(extra)
    return env
