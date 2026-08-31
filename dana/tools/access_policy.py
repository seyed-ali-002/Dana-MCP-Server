from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import (
    add_allowed_path,
    is_allowed,
    policy_status,
    remove_allowed_path,
    require_path,
    set_allowed_paths,
)


def register_access_policy_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_allowed_paths() -> dict:
        """Return Dana filesystem access policy. Empty allowed_paths means unrestricted except deny_paths."""
        return policy_status()

    @mcp.tool()
    def set_allowed_paths_tool(paths: list[str]) -> dict:
        """Replace allowed paths. An empty list grants unrestricted filesystem scope except explicit deny_paths."""
        return set_allowed_paths(paths)

    @mcp.tool()
    def add_allowed_path_tool(path: str) -> dict:
        """Add a directory or path to Dana's allowed filesystem scope."""
        return add_allowed_path(path)

    @mcp.tool()
    def remove_allowed_path_tool(path: str) -> dict:
        """Remove a path from Dana's allowed filesystem scope."""
        return remove_allowed_path(path)

    @mcp.tool()
    def validate_path_access(path: str) -> dict:
        """Check whether Dana is currently allowed to access a path."""
        try:
            target = require_path(path)
            return {"path": str(target), "allowed": True}
        except PermissionError as e:
            return {"path": path, "allowed": False, "reason": str(e)}
