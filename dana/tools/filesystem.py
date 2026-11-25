from pathlib import Path

from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import require_path
from dana.tools.mcp_quality import READ_ONLY, actionable_error


def register_filesystem_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY("List directory"))
    def list_directory(
        path: str = ".",
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, str | bool | int | float]]:
        """List directory entries with metadata (name, type, path, size, mtime, permissions).

        Relative paths resolve against cwd, home, and allowed roots.
        When allowed_paths is empty, all paths are permitted except deny_paths.
        limit defaults to 200 (max 500); use offset to page through large directories.
        For structured pagination metadata prefer workspace_snapshot.
        """
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))
        try:
            target = require_path(path, purpose="list directory")
        except PermissionError:
            raise
        try:
            if not target.exists():
                raise FileNotFoundError(actionable_error(
                    f"Path does not exist: {target}.",
                    next_steps=[
                        "Use an absolute path or a path under the project / home",
                        "Call dana_workspace_context to confirm cwd",
                    ],
                ))
            if not target.is_dir():
                raise ValueError(f"Not a directory: {target}")
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise PermissionError(actionable_error(
                f"OS denied access to directory {target}: {exc}.",
                next_steps=[
                    "Check filesystem permissions",
                    "If allowed_paths is set, add this root or clear it for full access",
                ],
            )) from exc

        entries: list[dict[str, str | bool | int | float]] = []
        try:
            items = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            raise PermissionError(actionable_error(
                f"OS denied listing {target}: {exc}.",
                next_steps=["Adjust OS ACL or Dana allowed_paths"],
            )) from exc

        for item in items[offset : offset + limit]:
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "path": str(item),
                    "size": stat.st_size,
                    "modified_time": stat.st_mtime,
                    "permissions": oct(stat.st_mode & 0o777),
                })
            except OSError as exc:
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "path": str(item),
                    "size": 0,
                    "modified_time": 0.0,
                    "permissions": "unknown",
                    "error": str(exc),
                })
        return entries
