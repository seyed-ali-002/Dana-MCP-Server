from pathlib import Path

from mcp.server.fastmcp import FastMCP


def register_filesystem_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_directory(path: str = ".") -> list[dict[str, str | bool]]:
        """List entries in a directory. Paths are resolved by the host OS."""
        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            raise ValueError(f"Not a directory: {target}")
        return [
            {"name": item.name, "is_dir": item.is_dir(), "path": str(item)}
            for item in sorted(target.iterdir(), key=lambda p: p.name.lower())
        ]
