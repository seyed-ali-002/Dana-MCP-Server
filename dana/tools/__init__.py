from mcp.server.fastmcp import FastMCP

from .filesystem import register_filesystem_tools
from .system import register_system_tools


def register_tools(mcp: FastMCP) -> None:
    register_system_tools(mcp)
    register_filesystem_tools(mcp)
