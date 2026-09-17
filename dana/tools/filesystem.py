from pathlib import Path

from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import require_path


def register_filesystem_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_directory(path: str = ".") -> list[dict[str, str | bool | int | float]]:
        """List directory entries with stable metadata: name, type, path, size, modified time, and permissions."""
        target = require_path(path, purpose="list directory")
        if not target.is_dir():
            raise ValueError(f"Not a directory: {target}")
        entries = []
        for item in sorted(target.iterdir(), key=lambda p: p.name.lower()):
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
