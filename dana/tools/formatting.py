from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 300) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return {"returncode": p.returncode, "stdout": p.stdout[-30000:], "stderr": p.stderr[-30000:], "command": cmd}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc), "command": cmd}


def _python_tool(module: str, args: list[str], cwd: str | None = None) -> dict[str, Any]:
    return _run([sys.executable, "-m", module, *args], cwd)


def register_formatting_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def format_python(path: str = ".", check: bool = False) -> dict[str, Any]:
        """Format Python code with Ruff formatter. Set check=true for a non-destructive check."""
        target = str(Path(path).expanduser().resolve())
        args = ["format", "--check"] if check else ["format"]
        args.append(target)
        return _python_tool("ruff", args, str(Path(target).parent if Path(target).is_file() else target))

    @mcp.tool()
    def lint_python(path: str = ".", fix: bool = False) -> dict[str, Any]:
        """Lint Python code with Ruff, optionally applying safe fixes."""
        target = str(Path(path).expanduser().resolve())
        args = ["check"]
        if fix:
            args.append("--fix")
        args.append(target)
        return _python_tool("ruff", args, str(Path(target).parent if Path(target).is_file() else target))

    @mcp.tool()
    def sort_python_imports(path: str = ".", check: bool = False) -> dict[str, Any]:
        """Sort Python imports using Ruff's isort-compatible rules (I)."""
        target = str(Path(path).expanduser().resolve())
        args = ["check", "--select", "I"]
        if not check:
            args.append("--fix")
        args.append(target)
        return _python_tool("ruff", args, str(Path(target).parent if Path(target).is_file() else target))

    @mcp.tool()
    def type_check_python(path: str = ".") -> dict[str, Any]:
        """Run mypy type checking when installed."""
        target = str(Path(path).expanduser().resolve())
        return _python_tool("mypy", [target], str(Path(target).parent if Path(target).is_file() else target))

    @mcp.tool()
    def check_code_quality(path: str = ".") -> dict[str, Any]:
        """Run a combined Python quality check: Ruff lint, formatting check, and optional mypy."""
        target = str(Path(path).expanduser().resolve())
        cwd = str(Path(target).parent if Path(target).is_file() else target)
        result = {
            "ruff_lint": _python_tool("ruff", ["check", target], cwd),
            "ruff_format": _python_tool("ruff", ["format", "--check", target], cwd),
        }
        if shutil.which("mypy") or __import__("importlib").util.find_spec("mypy"):
            result["mypy"] = _python_tool("mypy", [target], cwd)
        else:
            result["mypy"] = {"skipped": True, "reason": "mypy is not installed"}
        result["ok"] = all(v.get("returncode", 0) == 0 for v in result.values() if isinstance(v, dict) and "returncode" in v)
        return result

    @mcp.tool()
    def format_code(path: str = ".") -> dict[str, Any]:
        """Format a project based on detected files: Ruff for Python and Prettier for web/text files when available."""
        root = Path(path).expanduser().resolve()
        result: dict[str, Any] = {}
        if root.is_file() and root.suffix == ".py" or root.is_dir() and any(root.rglob("*.py")):
            result["python"] = format_python(str(root))
        prettier_files = []
        patterns = ("*.js", "*.jsx", "*.ts", "*.tsx", "*.json", "*.css", "*.html", "*.md", "*.yaml", "*.yml")
        if root.is_file() and root.suffix in {".js", ".jsx", ".ts", ".tsx", ".json", ".css", ".html", ".md", ".yaml", ".yml"}: prettier_files = [str(root)]
        elif root.is_dir():
            for pattern in patterns: prettier_files.extend(str(f) for f in root.rglob(pattern) if "node_modules" not in f.parts and ".git" not in f.parts)
        if prettier_files:
            if shutil.which("npx"):
                result["prettier"] = _run(["npx", "--yes", "prettier", "--write", *prettier_files], str(root.parent if root.is_file() else root))
            else:
                result["prettier"] = {"skipped": True, "reason": "npx/Prettier is not available"}
        result["ok"] = all(v.get("returncode", 0) == 0 for v in result.values() if isinstance(v, dict) and "returncode" in v)
        return result
