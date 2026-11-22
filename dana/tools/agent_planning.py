from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import require_path
from dana.subprocess_env import clean_subprocess_env


def register_agent_planning_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_task_plan(goal: str, steps: list[str]) -> dict[str, Any]:
        """Create a persistent step-by-step task plan in the workspace."""
        return {
            "goal": goal,
            "created_at": time.time(),
            "steps": [
                {"id": i + 1, "description": s, "status": "pending"}
                for i, s in enumerate(steps)
            ],
        }

    @mcp.tool()
    def task_status(plan: dict[str, Any]) -> dict[str, Any]:
        """Summarize progress of a plan created by create_task_plan."""
        steps = plan.get("steps", [])
        done = sum(x.get("status") == "done" for x in steps)
        return {
            "total": len(steps),
            "done": done,
            "pending": len(steps) - done,
            "complete": done == len(steps),
        }

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
        p = require_path(path, purpose="change_summary")
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
        p = require_path(path, purpose="workspace_snapshot")
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
    def rollback_changes(path: str = ".", hard: bool = False) -> dict[str, Any]:
        """Discard uncommitted Git changes. hard=true also removes untracked files (dangerous)."""
        p = require_path(path, purpose="rollback_changes")
        cmds = [["git", "restore", "."]]
        if hard:
            cmds.append(["git", "clean", "-fd"])
        results = []
        for c in cmds:
            r = subprocess.run(
                c, cwd=p, text=True, capture_output=True, env=clean_subprocess_env()
            )
            results.append(
                {"command": c, "returncode": r.returncode, "stderr": r.stderr}
            )
        return {"results": results, "ok": all(x["returncode"] == 0 for x in results)}

    @mcp.tool()
    def shell_probe(command: list[str], cwd: str = ".") -> dict[str, Any]:
        p = require_path(cwd, purpose="shell_probe cwd")
        r = subprocess.run(command, cwd=p, text=True, capture_output=True, env=clean_subprocess_env())
        return {
            "returncode": r.returncode,
            "stdout": (r.stdout or "")[:20000],
            "stderr": (r.stderr or "")[:20000],
        }
