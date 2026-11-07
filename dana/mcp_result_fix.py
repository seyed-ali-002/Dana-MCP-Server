"""MCP tool result normalization for strict clients (DeepSeek / SuperMCP).

Goals:
- If a tool advertises outputSchema, always send structuredContent.
- structuredContent is always a JSON object (dict) for maximum client compatibility.
- Errors are returned as CallToolResult(isError=True) so clients skip schema validation.
- Plain text / list / primitive returns are wrapped without raising.
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
    """Wrap any value into a JSON object — many clients reject non-object structuredContent."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload, "count": len(payload)}
    if payload is None:
        return {"ok": True}
    if isinstance(payload, (str, int, float, bool)):
        return {"result": payload}
    return {"result": payload}


def _text_from_content(content: Any) -> str:
    parts: list[str] = []
    for item in content or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def ensure_structured(result: Any, json_safe=None) -> Any:
    """Guarantee CallToolResult has structuredContent when the client expects a schema."""
    try:
        from mcp.types import CallToolResult, TextContent
    except Exception:
        return result

    def _build(content_items, structured, is_error: bool = False) -> Any:
        structured_obj = _as_object(_safe(structured, json_safe))
        try:
            return CallToolResult(
                content=content_items,
                structuredContent=structured_obj,
                isError=is_error,
            )
        except TypeError:
            try:
                return CallToolResult(
                    content=content_items,
                    structured_content=structured_obj,
                    isError=is_error,
                )
            except Exception:
                return result
        except Exception as exc:
            _log.debug("CallToolResult build failed: %s", exc)
            return result

    if isinstance(result, CallToolResult) or (
        hasattr(result, "content") and (
            hasattr(result, "structuredContent") or hasattr(result, "structured_content")
        )
    ):
        existing = getattr(result, "structuredContent", None)
        if existing is None:
            existing = getattr(result, "structured_content", None)
        is_error = bool(getattr(result, "isError", False) or getattr(result, "is_error", False))
        content = getattr(result, "content", None) or []
        if existing is not None:
            if isinstance(existing, dict):
                return result
            return _build(content, existing, is_error)
        text = _text_from_content(content)
        if text:
            try:
                structured = json.loads(text)
            except Exception:
                structured = {"text": text}
        else:
            structured = {"ok": not is_error}
        return _build(content, structured, is_error)

    safe = _safe(result, json_safe)
    try:
        text = json.dumps(safe, ensure_ascii=False, default=str)
    except Exception:
        text = str(result)
        safe = {"text": text}
    try:
        content = [TextContent(type="text", text=text)]
    except Exception:
        content = [{"type": "text", "text": text}]
    return _build(content, safe, False)


def error_result(message: str, *, detail: Any = None) -> Any:
    """Build an isError CallToolResult so clients skip outputSchema validation."""
    try:
        from mcp.types import CallToolResult, TextContent
    except Exception:
        payload = {"ok": False, "error": message}
        if detail is not None:
            payload["detail"] = str(detail)[:2000]
        return payload
    body: dict[str, Any] = {"ok": False, "error": message}
    if detail is not None:
        body["detail"] = _safe(detail) if not isinstance(detail, str) else detail[:2000]
    text = message if not detail else f"{message}\n{detail}"
    try:
        return CallToolResult(
            content=[TextContent(type="text", text=str(text)[:8000])],
            structuredContent=body,
            isError=True,
        )
    except TypeError:
        try:
            return CallToolResult(
                content=[TextContent(type="text", text=str(text)[:8000])],
                structured_content=body,
                isError=True,
            )
        except Exception:
            return body
    except Exception:
        return body


def strip_tool_output_schemas(mcp: Any) -> int:
    """Remove outputSchema from registered tools (DeepSeek / strict SuperMCP clients).

    Tools without a declared schema accept plain text / unstructured content.
    Controlled by DANA_STRIP_OUTPUT_SCHEMA (default: on).
    """
    import os
    flag = (os.getenv("DANA_STRIP_OUTPUT_SCHEMA") or "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return 0
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
