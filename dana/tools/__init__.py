from mcp.server.fastmcp import FastMCP

from .filesystem import register_filesystem_tools
from .system import register_system_tools
from .agent import register_agent_tools
from .web_quality_debug_docs import register_web_quality_debug_docs_tools
from .documents import register_document_tools
from .formatting import register_formatting_tools
from .advanced import register_advanced_tools
from .agent_planning import register_agent_planning_tools
from .access_policy import register_access_policy_tools
from .codebase_memory import register_codebase_memory_tools
from .docs_context import register_docs_context_tools
from .token_analytics import register_token_analytics_tools
from .optimization import register_optimization_tools
from .context_engine import register_context_tools


def register_tools(mcp: FastMCP) -> None:
    """Register every Dana capability with the MCP server."""
    register_system_tools(mcp)
    register_access_policy_tools(mcp)
    register_filesystem_tools(mcp)
    register_agent_tools(mcp)
    register_web_quality_debug_docs_tools(mcp)
    register_document_tools(mcp)
    register_formatting_tools(mcp)
    register_advanced_tools(mcp)
    register_agent_planning_tools(mcp)
    register_codebase_memory_tools(mcp)
    register_docs_context_tools(mcp)
    register_token_analytics_tools(mcp)
    register_context_tools(mcp)
    register_optimization_tools(mcp)
