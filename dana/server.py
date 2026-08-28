from mcp.server.fastmcp import FastMCP

from .tools import register_tools

mcp = FastMCP("Dana")
register_tools(mcp)
