from __future__ import annotations

from pathlib import Path
import subprocess
from dana.subprocess_env import clean_subprocess_env
from typing import Any

from mcp.server.fastmcp import FastMCP


def register_agent_planning_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def write_plan(title: str, steps: list[str], notes: str = "") -> dict[str, Any]:
        return {
            "title": title,
            "steps": [{"index": i + 1, "text": s} for i, s in enumerate(steps)],
            "notes": notes,
            "count": len(steps),
        }

    @mcp.tool()
    def task_breakdown(goal: str, max_steps: int = 8) -> dict[str, Any]:
        parts = [p.strip() for p in goal.replace(";", ".").split(".") if p.strip()]
        if not parts:
            parts = [goal.strip() or "Clarify the goal"]
        steps = parts[: max(1, min(max_steps, 20))]
        return {"goal": goal, "steps": steps, "count": len(steps)}

    @mcp.tool()
    def change_summary(path: str = ".") -> dict[str, Any]:
        p = Path(path).expanduser().resolve()
        r = subprocess.run(
            ["git", "status", "--short"], cwd=p, text=True, capture_output=True, env=clean_subprocess_env()
        )
        return {
            "returncode": r.returncode,
            "changes": r.stdout.splitlines(),
            "error": r.stderr,
        }

    @mcp.tool()
    def workspace_snapshot(path: str = ".") -> dict[str, Any]:
        p = Path(path).expanduser().resolve()
        r = subprocess.run(
            ["git", "status", "--short"], cwd=str(p), text=True, capture_output=True, env=clean_subprocess_env()
        )
        files = []
        try:
            for child in sorted(p.iterdir())[:80]:
                files.append({"name": child.name, "is_dir": child.is_dir()})
        except OSError as exc:
            return {"error": str(exc), "path": str(p)}
        return {
            "path": str(p),
            "entries": files,
            "git_status": r.stdout.splitlines() if r.returncode == 0 else [],
            "git_error": r.stderr if r.returncode else "",
        }

    @mcp.tool()
    def shell_probe(command: list[str], cwd: str = ".") -> dict[str, Any]:
        p = Path(cwd).expanduser().resolve()
        r = subprocess.run(command, cwd=p, text=True, capture_output=True, env=clean_subprocess_env())
        return {
            "returncode": r.returncode,
            "stdout": (r.stdout or "")[:20000],
            "stderr": (r.stderr or "")[:20000],
        }
