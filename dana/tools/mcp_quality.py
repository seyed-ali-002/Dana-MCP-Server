"""Dana-adapted MCP tool quality helpers (inspired by Anthropic mcp-builder).

Personalizations for Dana:
- Actionable errors that mention path policy / next tools.
- Pagination metadata for list payloads.
- Annotation presets (read-only / destructive / mutating / open-world).
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

try:
    from mcp.types import ToolAnnotations
except Exception:  # pragma: no cover
    ToolAnnotations = None  # type: ignore


def ann(
    *,
    read_only: bool | None = None,
    destructive: bool | None = None,
    idempotent: bool | None = None,
    open_world: bool | None = None,
    title: str | None = None,
):
    if ToolAnnotations is None:
        return None
    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


def READ_ONLY(title: str | None = None):
    return ann(read_only=True, destructive=False, idempotent=True, open_world=False, title=title)


def DESTRUCTIVE(title: str | None = None):
    return ann(read_only=False, destructive=True, idempotent=False, open_world=False, title=title)


def MUTATING(title: str | None = None):
    return ann(read_only=False, destructive=False, idempotent=False, open_world=False, title=title)


def OPEN_WORLD(title: str | None = None):
    return ann(read_only=True, destructive=False, idempotent=True, open_world=True, title=title)


def paginate(
    items: Sequence[Any] | Iterable[Any],
    *,
    limit: int = 50,
    offset: int = 0,
    max_limit: int = 200,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), max_limit))
    offset = max(0, int(offset or 0))
    if not isinstance(items, Sequence):
        items = list(items)
    total = len(items)
    window = list(items[offset : offset + limit])
    next_offset = offset + len(window)
    return {
        "items": window,
        "count": len(window),
        "total_count": total,
        "limit": limit,
        "offset": offset,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
    }


def actionable_error(
    message: str,
    *,
    next_steps: list[str] | None = None,
    related_tools: list[str] | None = None,
) -> str:
    parts = [message.rstrip()]
    if next_steps:
        parts.append("Next: " + "; ".join(next_steps))
    if related_tools:
        parts.append("Related tools: " + ", ".join(related_tools))
    return " ".join(parts)
