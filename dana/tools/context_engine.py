from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

STATE = Path(__file__).resolve().parents[2] / ".dana"
DB = STATE / "context_engine.db"
MAX_CONTEXT_CHARS = 120_000
MAX_RESULT_CHARS = 24_000
DEFAULT_PAGE_SIZE = 100
_CACHE: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_CACHE_LIMIT = 256


def _db() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL, summary TEXT NOT NULL DEFAULT '')"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS context_cache(key TEXT PRIMARY KEY, created REAL NOT NULL, expires REAL NOT NULL, payload TEXT NOT NULL)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY, created REAL NOT NULL, payload TEXT NOT NULL)"
    )
    c.commit()
    return c


def _hash(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _tokens(value: Any) -> int:
    raw = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    return max(0, (len(raw) + 3) // 4)


def _compact_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    text = re.sub(r"[ \t]{2,}", " ", text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def optimize_result(value: Any, max_chars: int = MAX_RESULT_CHARS) -> Any:
    """Loss-aware result normalization: remove repeated whitespace and cap huge leaf text."""
    if isinstance(value, str):
        return _compact_text(value, max_chars)
    if isinstance(value, list):
        if len(value) > DEFAULT_PAGE_SIZE:
            return {
                "items": value[:DEFAULT_PAGE_SIZE],
                "next_cursor": _store_page(value[DEFAULT_PAGE_SIZE:]),
                "truncated": True,
            }
        return [
            optimize_result(
                x, max_chars // 2 if isinstance(x, (dict, list)) else max_chars
            )
            for x in value
        ]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out[str(key)] = optimize_result(
                item, max_chars // 2 if isinstance(item, (dict, list)) else max_chars
            )
        return out
    return value


def _store_page(items: list[Any]) -> str:
    cursor = _hash({"items": items, "ts": time.time_ns()})[:32]
    c = _db()
    c.execute(
        "INSERT OR REPLACE INTO pages(id,created,payload) VALUES(?,?,?)",
        (cursor, time.time(), json.dumps(items, ensure_ascii=False, default=str)),
    )
    c.commit()
    c.close()
    return cursor


def read_page(cursor: str, page_size: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    c = _db()
    row = c.execute("SELECT payload FROM pages WHERE id=?", (cursor,)).fetchone()
    c.close()
    if not row:
        raise ValueError("Unknown or expired page cursor")
    items = json.loads(row[0])
    page_size = max(1, min(page_size, 500))
    page = items[:page_size]
    rest = items[page_size:]
    next_cursor = _store_page(rest) if rest else None
    return {"items": page, "count": len(page), "next_cursor": next_cursor}


def create_session(session_id: str) -> dict[str, Any]:
    now = time.time()
    c = _db()
    c.execute(
        "INSERT OR IGNORE INTO sessions(id,created,updated,summary) VALUES(?,?,?,?)",
        (session_id, now, now, ""),
    )
    c.execute("UPDATE sessions SET updated=? WHERE id=?", (now, session_id))
    c.commit()
    c.close()
    return {"session_id": session_id, "created_or_updated": True}


def compact_session(
    session_id: str, messages: list[str], max_chars: int = 16000
) -> dict[str, Any]:
    create_session(session_id)
    unique = list(dict.fromkeys(m.strip() for m in messages if m and m.strip()))
    summary = _compact_text("\n".join(unique), max_chars)
    c = _db()
    c.execute(
        "UPDATE sessions SET summary=?,updated=? WHERE id=?",
        (summary, time.time(), session_id),
    )
    c.commit()
    c.close()
    return {
        "session_id": session_id,
        "summary": summary,
        "source_messages": len(messages),
        "summary_tokens_est": _tokens(summary),
    }


def get_session(session_id: str) -> dict[str, Any]:
    c = _db()
    row = c.execute(
        "SELECT created,updated,summary FROM sessions WHERE id=?", (session_id,)
    ).fetchone()
    c.close()
    if not row:
        return {"session_id": session_id, "exists": False}
    return {
        "session_id": session_id,
        "exists": True,
        "created": row[0],
        "updated": row[1],
        "summary": row[2],
    }


def build_context(
    static: Any,
    dynamic: Any,
    history_summary: str = "",
    current: Any = None,
    budget_tokens: int = 32000,
) -> dict[str, Any]:
    budget = max(1000, min(int(budget_tokens), 200000))
    result = {
        "static": static,
        "history_summary": history_summary,
        "dynamic": dynamic,
        "current": current,
    }
    while _tokens(result) > budget and result.get("dynamic"):
        result["dynamic"] = optimize_result(
            result["dynamic"],
            max(1000, len(json.dumps(result["dynamic"], default=str)) // 2),
        )
        if _tokens(result) > budget and result.get("history_summary"):
            result["history_summary"] = _compact_text(
                result["history_summary"],
                max(1000, len(result["history_summary"]) // 2),
            )
        else:
            break
    return {
        "context": result,
        "tokens_est": _tokens(result),
        "budget_tokens": budget,
        "within_budget": _tokens(result) <= budget,
    }


def cache_get(key: str) -> Any | None:
    now = time.time()
    item = _CACHE.get(key)
    if item and item[0] > now:
        _CACHE.move_to_end(key)
        return item[1]
    if item:
        _CACHE.pop(key, None)
    return None


def cache_put(key: str, value: Any, ttl: int = 300) -> None:
    _CACHE[key] = (time.time() + max(1, ttl), value)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)


def register_context_tools(mcp: Any) -> None:
    @mcp.tool()
    def dana_context_compact(
        messages: list[str], max_chars: int = 16000
    ) -> dict[str, Any]:
        """Compact repeated conversation/context text into a bounded summary."""
        return compact_session("ad_hoc", messages, max_chars)

    @mcp.tool()
    def dana_context_build(
        static: Any = None,
        dynamic: Any = None,
        history_summary: str = "",
        current: Any = None,
        budget_tokens: int = 32000,
    ) -> dict[str, Any]:
        """Build a deterministic context under a token budget; stable data stays before dynamic data."""
        return build_context(static, dynamic, history_summary, current, budget_tokens)

    @mcp.tool()
    def dana_session_start(session_id: str) -> dict[str, Any]:
        """Create or refresh a persistent optimization session."""
        return create_session(session_id)

    @mcp.tool()
    def dana_session_compact(
        session_id: str, messages: list[str], max_chars: int = 16000
    ) -> dict[str, Any]:
        """Persist a compact summary for a long-running Dana session."""
        return compact_session(session_id, messages, max_chars)

    @mcp.tool()
    def dana_session_get(session_id: str) -> dict[str, Any]:
        """Return the current compact summary of an optimization session."""
        return get_session(session_id)

    @mcp.tool()
    def dana_result_page(cursor: str, page_size: int = 100) -> dict[str, Any]:
        """Read the next page from a large Dana result using a cursor."""
        return read_page(cursor, page_size)

    @mcp.tool()
    def dana_result_optimize(
        value: Any, max_chars: int = MAX_RESULT_CHARS
    ) -> dict[str, Any]:
        """Normalize and compact a large tool result while preserving its structure."""
        optimized = optimize_result(value, max_chars)
        return {
            "result": optimized,
            "input_tokens_est": _tokens(value),
            "output_tokens_est": _tokens(optimized),
            "saved_tokens_est": max(0, _tokens(value) - _tokens(optimized)),
        }
