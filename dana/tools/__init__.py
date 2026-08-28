from mcp.server.fastmcp import FastMCP

from .filesystem import register_filesystem_tools
from .system import register_system_tools
from .agent import register_agent_tools
from .web_quality_debug_docs import register_web_quality_debug_docs_tools


def register_tools(mcp: FastMCP) -> None:
    """Register every Dana capability with the MCP server."""
    register_system_tools(mcp)
    register_filesystem_tools(mcp)
    register_agent_tools(mcp)
    register_web_quality_debug_docs_tools(mcp)
