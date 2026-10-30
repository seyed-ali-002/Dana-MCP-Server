from pathlib import Path

from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import require_path


def register_filesystem_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_directory(path: str = ".") -> list[dict[str, str | bool | int | float]]:
        """List directory entries with stable metadata: name, type, path, size, modified time, and permissions.

        Relative paths resolve against the process cwd, home directory, and allowed roots.
        When allowed_paths is empty, all paths are permitted except deny_paths.
        """
        try:
            target = require_path(path, purpose="list directory")
        except PermissionError:
            raise
        try:
            if not target.is_dir():
                raise ValueError(f"Not a directory: {target}")
        except OSError as exc:
            raise PermissionError(
                f"OS denied access to directory {target!s}: {exc}. "
                f"Check filesystem permissions or Dana allowed_paths."
            ) from exc

        entries: list[dict[str, str | bool | int | float]] = []
        try:
            items = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            raise PermissionError(
                f"OS denied listing {target!s}: {exc}. "
                f"If this is unexpected and allowed_paths is set, add this root or clear allowed_paths for full access."
            ) from exc

        for item in items:
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
