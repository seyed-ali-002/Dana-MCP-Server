"""MCP tool result normalization for strict clients (DeepSeek / SuperMCP).

Goals:
- structuredContent is always a JSON object (dict) for maximum client compatibility.
- Errors are returned as CallToolResult(isError=True) so clients skip schema validation.
- Plain text / list / primitive returns are wrapped without raising.
- Error messages can include next-step guidance for agents.
"""
from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger("dana.mcp_result")


def _safe(value: Any, json_safe=None) -> Any:
    if json_safe is not None:
        try:
            return json_safe(value)
        except Exception:
            pass
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v, json_safe) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v, json_safe) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _safe(value.model_dump(mode="json"), json_safe)
        except Exception:
            pass
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return text
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _as_object(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload, "count": len(payload)}
    if payload is None:
        return {"ok": True, "value": None}
    return {"value": payload}


def ensure_structured(result: Any, json_safe=None) -> Any:
    """Normalize a tool return value into CallToolResult with object structuredContent."""
    if result is not None and hasattr(result, "content") and hasattr(result, "isError"):
        return result
    try:
        from mcp.types import CallToolResult, TextContent
    except Exception:
        return result

    payload = _as_object(_safe(result, json_safe))
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        text = str(payload)
    try:
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structuredContent=payload,
            isError=False,
        )
    except TypeError:
        return CallToolResult(content=[TextContent(type="text", text=text)], isError=False)


def error_result(
    message: str,
    *,
    detail: Any = None,
    next_steps: list[str] | None = None,
) -> Any:
    """Build an isError CallToolResult with optional next-step guidance."""
    try:
        from mcp.types import CallToolResult, TextContent
    except Exception:
        body = {"error": message, "detail": detail, "next_steps": next_steps or []}
        return body

    parts = [str(message)]
    if next_steps:
        parts.append("Next: " + "; ".join(next_steps))
    text = " ".join(parts)
    payload: dict[str, Any] = {"error": str(message), "ok": False}
    if detail is not None:
        payload["detail"] = _safe(detail)
    if next_steps:
        payload["next_steps"] = list(next_steps)
    try:
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structuredContent=payload,
            isError=True,
        )
    except TypeError:
        return CallToolResult(content=[TextContent(type="text", text=text)], isError=True)


def strip_output_schemas(mcp: Any) -> int:
    """Best-effort clear of advertised outputSchema on registered tools (compat mode)."""
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None:
        return 0
    tools = []
    for attr in ("_tools", "tools"):
        bucket = getattr(manager, attr, None)
        if isinstance(bucket, dict):
            tools = list(bucket.values())
            break
        if isinstance(bucket, list):
            tools = list(bucket)
            break
    if not tools and hasattr(manager, "list_tools"):
        try:
            listed = manager.list_tools()
            tools = list(listed) if listed else []
        except Exception:
            tools = []
    cleared = 0
    for tool in tools:
        for field in ("output_schema", "outputSchema", "output_model"):
            if hasattr(tool, field) and getattr(tool, field) is not None:
                try:
                    setattr(tool, field, None)
                    cleared += 1
                except Exception:
                    pass
        meta = getattr(tool, "meta", None) or getattr(tool, "_meta", None)
        if isinstance(meta, dict) and meta.get("outputSchema"):
            meta.pop("outputSchema", None)
            cleared += 1
        fn_meta = getattr(tool, "fn_metadata", None) or getattr(tool, "func_metadata", None)
        if fn_meta is not None:
            for field in ("output_schema", "outputSchema", "structured_output"):
                if hasattr(fn_meta, field):
                    try:
                        setattr(fn_meta, field, None if field != "structured_output" else False)
                        cleared += 1
                    except Exception:
                        pass
    if cleared:
        _log.info("Stripped outputSchema from tools (%s fields cleared)", cleared)
    return cleared
