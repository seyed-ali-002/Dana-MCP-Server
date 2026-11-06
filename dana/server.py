#!/usr/bin/env python3
"""Dana MCP server — body is stored base64-adjacent to keep packaging simple."""
from __future__ import annotations

from pathlib import Path
import base64
import sys
import types

_HERE = Path(__file__).resolve().parent
_B64 = _HERE / "server.py.b64"
if not _B64.is_file():
    raise RuntimeError("Missing dana/server.py.b64 — reinstall Dana or restore from the repository.")
_CODE = base64.b64decode("".join(_B64.read_text(encoding="ascii").split()))
_MOD = types.ModuleType(__name__)
_MOD.__file__ = str(_HERE / "server_body.py")
_MOD.__package__ = __package__
sys.modules[__name__] = _MOD
exec(compile(_CODE, str(_HERE / "server_body.py"), "exec"), _MOD.__dict__)
# Re-export public names for `from dana.server import mcp`
globals().update({k: v for k, v in _MOD.__dict__.items() if not k.startswith("_")})
