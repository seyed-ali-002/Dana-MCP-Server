from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import require_path
from dana.subprocess_env import clean_subprocess_env
from dana.tools.mcp_quality import DESTRUCTIVE, MUTATING, READ_ONLY, actionable_error, paginate


def register_agent_planning_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY("Create task plan"))
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

    @mcp.tool(annotations=READ_ONLY("Task status"))
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

    @mcp.tool(annotations=READ_ONLY("Write plan outline"))
    def write_plan(title: str, steps: list[str], notes: str = "") -> dict[str, Any]:
        """Build a lightweight titled plan outline (not persisted)."""
        return {
            "title": title,
            "steps": [{"index": i + 1, "text": s} for i, s in enumerate(steps)],
            "notes": notes,
            "count": len(steps),
        }

    @mcp.tool(annotations=READ_ONLY("Break goal into steps"))
    def task_breakdown(goal: str, max_steps: int = 8) -> dict[str, Any]:
        """Heuristically split a goal into ordered steps (no model call)."""
        parts = [p.strip() for p in goal.replace(";", ".").split(".") if p.strip()]
        if not parts:
            parts = [goal.strip() or "Clarify the goal"]
        steps = parts[: max(1, min(max_steps, 20))]
        return {"goal": goal, "steps": steps, "count": len(steps)}

    @mcp.tool(annotations=READ_ONLY("Git change summary"))
    def change_summary(path: str = ".") -> dict[str, Any]:
        """Return git status --short under Dana path policy."""
        p = require_path(path, purpose="change_summary")
        r = subprocess.run(
            ["git", "status", "--short"], cwd=p, text=True, capture_output=True, env=clean_subprocess_env()
        )
        return {
            "returncode": r.returncode,
            "changes": r.stdout.splitlines(),
            "error": r.stderr,
        }

    @mcp.tool(annotations=READ_ONLY("Workspace snapshot"))
    def workspace_snapshot(path: str = ".", limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List directory entries plus optional git status (paginated)."""
        p = require_path(path, purpose="workspace_snapshot")
        r = subprocess.run(
            ["git", "status", "--short"], cwd=str(p), text=True, capture_output=True, env=clean_subprocess_env()
        )
        try:
            children = sorted(p.iterdir(), key=lambda c: c.name.lower())
        except OSError as exc:
            raise PermissionError(actionable_error(f"Cannot list {p}: {exc}", next_steps=["Check permissions/allowed_paths"])) from exc
        files = [{"name": c.name, "is_dir": c.is_dir()} for c in children]
        page = paginate(files, limit=limit, offset=offset)
        return {
            "path": str(p),
            **page,
            "entries": page["items"],
            "git_status": r.stdout.splitlines() if r.returncode == 0 else [],
            "git_error": (r.stderr or "").strip() if r.returncode else "",
        }

    @mcp.tool(annotations=DESTRUCTIVE("Rollback git changes"))
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

    @mcp.tool(annotations=MUTATING("Shell probe"))
    def shell_probe(command: list[str], cwd: str = ".") -> dict[str, Any]:
        """Run argv list under path policy (no shell expansion). Prefer specialized tools."""
        if not command or not isinstance(command, list):
            raise ValueError(actionable_error("command must be non-empty argv list", related_tools=["change_summary"]))
        p = require_path(cwd, purpose="shell_probe cwd")
        r = subprocess.run(command, cwd=p, text=True, capture_output=True, env=clean_subprocess_env())
        return {
            "returncode": r.returncode,
            "stdout": (r.stdout or "")[:20000],
            "stderr": (r.stderr or "")[:20000],
        }
