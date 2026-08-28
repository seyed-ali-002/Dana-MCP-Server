import platform
import sys

from mcp.server.fastmcp import FastMCP


def register_system_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def system_info() -> dict[str, str]:
        """Return basic information about the host running Dana."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "python": sys.version.split()[0],
            "hostname": platform.node(),
        }
