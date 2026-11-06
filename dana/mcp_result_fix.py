"""Ensure MCP tool results always include structuredContent (DeepSeek / SuperMCP)."""
from __future__ import annotations

import json
from typing import Any


def ensure_structured(result: Any, json_safe=None) -> Any:
    try:
        from mcp.types import CallToolResult, TextContent
    except Exception:
        return result
    if json_safe is None:
        json_safe = lambda v: v
    if isinstance(result, CallToolResult):
        if getattr(result, "structuredContent", None) is not None:
            return result
        texts = []
        for item in (result.content or []):
            text = getattr(item, "text", None)
            if isinstance(text, str):
                texts.append(text)
        if texts:
            joined = "\n".join(texts)
            try:
                structured = json.loads(joined)
            except Exception:
                structured = {"text": joined}
        else:
            structured = {"ok": True}
        try:
            return CallToolResult(
                content=result.content,
                structuredContent=structured,
                isError=bool(getattr(result, "isError", False)),
            )
        except Exception:
            return result
    if isinstance(result, (dict, list)):
        try:
            text = json.dumps(json_safe(result), ensure_ascii=False, default=str)
            return CallToolResult(
                content=[TextContent(type="text", text=text)],
                structuredContent=json_safe(result),
                isError=False,
            )
        except Exception:
            return result
    return result
