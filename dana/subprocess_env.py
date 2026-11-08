"""Clean environment for child processes spawned from PyInstaller/AppImage builds.

PyInstaller sets LD_LIBRARY_PATH to its extracted _MEI folder. Passing that to
system binaries (curl, git, python3, node) causes OPENSSL version mismatches and
\"unknown url type: https\" errors. Always scrub these vars for external commands.
"""
from __future__ import annotations

import os
from typing import Mapping


_SCRUB_KEYS = (
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONNOUSERSITE",
)


def clean_subprocess_env(
    base: Mapping[str, str] | None = None,
    *,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an env dict safe for system subprocesses.

    Removes PyInstaller / embedded-Python leakage. Optionally restores values
    from DANA_HOST_* overrides (e.g. DANA_HOST_LD_LIBRARY_PATH).
    """
    src = dict(base if base is not None else os.environ)
    env = {k: v for k, v in src.items() if k not in _SCRUB_KEYS}
    for key in _SCRUB_KEYS:
        host = os.environ.get(f"DANA_HOST_{key}")
        if host is not None and host != "":
            env[key] = host
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


# Back-compat alias used in older patches / supermcp
_clean_subprocess_env = clean_subprocess_env
