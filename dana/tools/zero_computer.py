"""Optional bridge to Zero Use Computer if installed on PATH."""
from __future__ import annotations

import shutil
import subprocess
from typing import Any

from mcp.server.fastmcp import FastMCP


def register_zero_computer_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def zero_computer(command: str = "status", args: str = "") -> dict[str, Any]:
        """Call the optional Zero Use Computer CLI if installed (https://github.com/mhrsdev/zero-use-computer).

        Install the upstream binary separately, then use this bridge. Without it, use Dana desktop_control.
        """
        binary = shutil.which("zero") or shutil.which("zero-use-computer")
        if not binary:
            return {
                "ok": False,
                "installed": False,
                "message": "Zero Use Computer is not installed. Download from GitHub releases or use desktop_control.",
            }
        cmd = [binary]
        if command and command != "status":
            cmd.append(command)
        if args.strip():
            cmd.extend(args.split())
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as exc:
            return {"ok": False, "installed": True, "error": str(exc)}
        return {
            "ok": result.returncode == 0,
            "installed": True,
            "returncode": result.returncode,
            "stdout": (result.stdout or "")[:20000],
            "stderr": (result.stderr or "")[:4000],
        }
