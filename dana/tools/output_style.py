from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


def register_output_style_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_compact_response(
        answer: str,
        next_action: str = "",
        progress: str = "",
        error: str = "",
    ) -> dict[str, Any]:
        """Package an agent result in an action-first, compact and scannable response shape."""
        result: dict[str, Any] = {"answer": answer.strip()}
        if progress:
            result["progress"] = progress.strip()
        if error:
            result["error"] = error.strip()
        if next_action:
            result["next_action"] = next_action.strip()
        return result
