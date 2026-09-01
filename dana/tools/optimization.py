#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .context_engine import _hash, optimize_result
from .performance_engine import semantic_get, semantic_put

_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = _ROOT / ".dana"
_DB = _STATE_DIR / "optimization.db"

# Only inexpensive/read-oriented operations are cached. Mutating, network,
# process-control, package-manager, git and build tools are deliberately excluded.
_CACHE_TTLS = {
    "system_info": 2.0,
    "system_metrics": 2.0,
    "process_list": 1.0,
    "toolchain_status": 10.0,
    "codebase_memory_status": 5.0,
    "list_directory": 1.0,
    "database_schema": 5.0,
    "architecture_summary": 10.0,
}
_CACHE_MAX_ITEMS = 256
_CACHE_ENABLED = os.getenv("DANA_TOOL_CACHE", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_RESULT_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_HITS = 0
_CACHE_MISSES = 0


def _db() -> sqlite3.Connection:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            tool TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            duration_ms REAL NOT NULL,
            cached INTEGER NOT NULL DEFAULT 0,
            batch INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 1
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_ts ON calls(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_tool ON calls(tool)")
    conn.commit()
    return conn


def estimate_tokens(value: Any) -> int:
    """Fast provider-independent estimate used only for local optimization telemetry."""
    if value is None:
        return 0
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(
                value, ensure_ascii=False, default=str, separators=(",", ":")
            )
        except (TypeError, ValueError):
            text = str(value)
    return max(0, (len(text) + 3) // 4)


def _tool_cache_key(name: str, arguments: dict[str, Any]) -> str:
    payload = json.dumps(
        arguments or {},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{name}\0{payload}".encode()).hexdigest()


def _cached(name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
    global _CACHE_HITS, _CACHE_MISSES
    if not _CACHE_ENABLED:
        return False, None
    ttl = _CACHE_TTLS.get(name)
    if not ttl:
        return False, None
    key = _tool_cache_key(name, arguments)
    item = _RESULT_CACHE.get(key)
    if item and time.monotonic() - item[0] < ttl:
        _CACHE_HITS += 1
        return True, item[1]
    _CACHE_MISSES += 1
    _RESULT_CACHE.pop(key, None)
    return False, None


def _store_cache(name: str, arguments: dict[str, Any], result: Any) -> None:
    if not _CACHE_ENABLED:
        return
    ttl = _CACHE_TTLS.get(name)
    if not ttl:
        return
    if len(_RESULT_CACHE) >= _CACHE_MAX_ITEMS:
        oldest = min(_RESULT_CACHE.items(), key=lambda item: item[1][0])[0]
        _RESULT_CACHE.pop(oldest, None)
    _RESULT_CACHE[_tool_cache_key(name, arguments)] = (time.monotonic(), result)


def _compact_description(description: str | None) -> str:
    text = re.sub(r"\s+", " ", description or "").strip()
    # Keep useful semantics but avoid huge docstrings becoming tool metadata.
    return text[:280] + ("…" if len(text) > 280 else "")


def _catalog(mcp: FastMCP) -> tuple[list[Any], str]:
    tools = list(mcp._tool_manager._tools.values())
    tools.sort(key=lambda tool: tool.name)
    fingerprint_payload = [
        {
            "name": t.name,
            "description": _compact_description(t.description),
            "parameters": t.parameters,
        }
        for t in tools
    ]
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return tools, fingerprint


def _search_score(name: str, description: str, query: str) -> int:
    q = [x for x in re.split(r"[^a-zA-Z0-9_]+", query.lower()) if x]
    hay = f"{name} {description}".lower()
    score = 0
    for token in q:
        if token == name.lower():
            score += 100
        elif name.lower().startswith(token):
            score += 30
        elif token in name.lower():
            score += 20
        elif token in hay:
            score += 5
    return score


def _visible_names(mcp: FastMCP) -> set[str]:
    # Keep MCP discovery tiny. These are the control-plane tools; all other
    # capabilities remain registered and executable through dana_call_tool.
    return {
        "dana_search_tools",
        "dana_call_tool",
        "dana_batch_call",
        "dana_capabilities",
        "dana_optimization_stats",
        "dana_context_build",
        "dana_context_compact",
        "dana_result_page",
        "dana_result_optimize",
        "dana_session_start",
        "dana_session_compact",
        "dana_session_get",
        "dana_prompt_cache_key",
    }


def register_optimization_tools(mcp: FastMCP) -> None:
    """Install progressive discovery, batching, caching, context optimization and telemetry."""

    @mcp.tool()
    def dana_prompt_cache_key(
        static_context: Any = None, tool_registry_version: str = ""
    ) -> dict[str, Any]:
        """Create a stable cache key for provider prompt-caching prefixes."""
        key = _hash(
            {
                "static_context": static_context,
                "tool_registry_version": tool_registry_version,
            }
        )
        return {
            "cache_key": key,
            "prefix_stable": True,
            "hint": "Keep dynamic state and current user input after this prefix.",
        }

    @mcp.tool()
    def dana_search_tools(query: str, limit: int = 6) -> dict[str, Any]:
        """Find Dana capabilities by name or purpose. Returns compact schemas for the best matches."""
        cached = semantic_get(f"tool-search:{query}", ttl=15)
        if cached is not None:
            return cached
        tools, fingerprint = _catalog(mcp)
        query = query.strip()
        limit = max(1, min(limit, 12))
        ranked = []
        for tool in tools:
            score = _search_score(tool.name, tool.description, query)
            if score:
                ranked.append((score, tool))
        ranked.sort(key=lambda item: (-item[0], item[1].name))
        results = [
            {
                "name": tool.name,
                "description": _compact_description(tool.description),
                "input_schema": tool.parameters,
                "cached": tool.name in _CACHE_TTLS,
            }
            for _, tool in ranked[:limit]
        ]
        response = {
            "query": query,
            "matches": results,
            "count": len(results),
            "registry_version": fingerprint[:16],
            "hint": "Call dana_call_tool with the selected name and arguments.",
        }
        semantic_put(f"tool-search:{query}", response, ttl=15)
        return response

    manager = mcp._tool_manager
    raw_call_tool = manager.call_tool

    @mcp.tool()
    async def dana_call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Execute any Dana capability by exact tool name. Use dana_search_tools when the name or arguments are unknown."""
        target = name.strip()
        if target in {"dana_call_tool", "dana_batch_call"}:
            raise ValueError("Recursive gateway invocation is not allowed")
        if target not in mcp._tool_manager._tools:
            raise ValueError(f"Unknown Dana tool: {target}")
        args = arguments or {}
        hit, cached = _cached(target, args)
        if hit:
            return cached
        started = time.perf_counter()
        success = True
        result: Any = None
        try:
            result = await raw_call_tool(
                target, args, context=None, convert_result=False
            )
            result = optimize_result(result)
            _store_cache(target, args, result)
            return result
        except Exception:
            success = False
            raise
        finally:
            duration = (time.perf_counter() - started) * 1000
            conn = _db()
            conn.execute(
                "INSERT INTO calls(ts,tool,input_tokens,output_tokens,duration_ms,cached,batch,success) VALUES(?,?,?,?,?,?,?,?)",
                (
                    time.time(),
                    target,
                    estimate_tokens(args),
                    estimate_tokens(result),
                    duration,
                    0,
                    0,
                    int(success),
                ),
            )
            conn.commit()
            conn.close()

    @mcp.tool()
    async def dana_batch_call(
        calls: list[dict[str, Any]], parallel: bool = True
    ) -> dict[str, Any]:
        """Execute multiple independent Dana capabilities; set parallel=false when calls have dependencies or mutate shared state."""
        if not calls:
            return {"results": [], "count": 0}
        if len(calls) > 16:
            raise ValueError("A batch may contain at most 16 calls")

        async def one(item: dict[str, Any]) -> dict[str, Any]:
            name = str(item.get("name", "")).strip()
            args = item.get("arguments") or {}
            if (
                not name
                or name.startswith("dana_")
                or name not in mcp._tool_manager._tools
            ):
                return {
                    "name": name,
                    "ok": False,
                    "error": "Unknown or unsupported tool",
                }
            hit, cached = _cached(name, args)
            if hit:
                return {"name": name, "ok": True, "cached": True, "result": cached}
            try:
                result = await raw_call_tool(
                    name, args, context=None, convert_result=False
                )
                _store_cache(name, args, result)
                return {"name": name, "ok": True, "cached": False, "result": result}
            except (ValueError, RuntimeError, OSError) as exc:
                return {"name": name, "ok": False, "error": str(exc)}

        if parallel:
            results = await asyncio.gather(*(one(item) for item in calls))
        else:
            results = []
            for item in calls:
                results.append(await one(item))
        return {"results": results, "count": len(results), "parallel": parallel}

    @mcp.tool()
    def dana_capabilities() -> dict[str, Any]:
        """Return a compact overview of Dana's full capability registry."""
        tools, fingerprint = _catalog(mcp)
        full_tokens = estimate_tokens(
            [
                {
                    "name": t.name,
                    "description": _compact_description(t.description),
                    "input_schema": t.parameters,
                }
                for t in tools
            ]
        )
        visible = [t for t in tools if t.name in _visible_names(mcp)]
        visible_tokens = estimate_tokens(
            [
                {
                    "name": t.name,
                    "description": _compact_description(t.description),
                    "input_schema": t.parameters,
                }
                for t in visible
            ]
        )
        categories = Counter(
            tool.name.split("_", 1)[0]
            for tool in tools
            if not tool.name.startswith("dana_")
        )
        return {
            "tool_count": len([t for t in tools if not t.name.startswith("dana_")]),
            "registry_version": fingerprint,
            "tool_definition_tokens": {
                "full_estimate": full_tokens,
                "visible_estimate": visible_tokens,
                "estimated_savings": max(0, full_tokens - visible_tokens),
                "estimated_reduction_percent": round(
                    max(0, 100 * (full_tokens - visible_tokens) / full_tokens), 2
                )
                if full_tokens
                else 0,
            },
            "categories": dict(sorted(categories.items())),
            "progressive_discovery": os.getenv("DANA_PROGRESSIVE_TOOLS", "1")
            .strip()
            .lower()
            not in {"0", "false", "no", "off"},
            "visible_tools": sorted(_visible_names(mcp)),
            "cacheable_tools": sorted(_CACHE_TTLS),
        }

    @mcp.tool()
    def dana_optimization_stats() -> dict[str, Any]:
        """Return optimization, cache, timing and token-estimate statistics."""
        conn = _db()
        row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0),COALESCE(SUM(duration_ms),0),COUNT(*) FROM calls"
        ).fetchone()
        by_tool = conn.execute(
            "SELECT tool,COUNT(*),COALESCE(SUM(duration_ms),0) FROM calls GROUP BY tool ORDER BY COUNT(*) DESC LIMIT 20"
        ).fetchall()
        conn.close()
        return {
            "cache": {
                "hits": _CACHE_HITS,
                "misses": _CACHE_MISSES,
                "entries": len(_RESULT_CACHE),
            },
            "calls": {
                "input_tokens_est": row[0],
                "output_tokens_est": row[1],
                "duration_ms": row[2],
                "operations": row[3],
            },
            "top_tools": [
                {"name": r[0], "operations": r[1], "duration_ms": r[2]} for r in by_tool
            ],
        }


    @mcp.tool()
    async def dana_route_request(query: str, limit: int = 6) -> dict[str, Any]:
        """Route a request to a safe fast-path or the smallest relevant tool set."""
        text = query.strip().lower()
        fast = {
            "git status": ("change_summary", {}),
            "show git status": ("change_summary", {}),
            "server status": ("system_metrics", {}),
            "system metrics": ("system_metrics", {}),
            "system info": ("system_info", {}),
            "list processes": ("process_list", {}),
            "processes": ("process_list", {}),
            "toolchain status": ("toolchain_status", {}),
        }
        if text in fast and fast[text][0] in mcp._tool_manager._tools:
            name, arguments = fast[text]
            return {"mode": "fast_path", "tool": name, "arguments": arguments}
        found = dana_search_tools(query, limit)
        return {"mode": "tool_search", "query": query, "matches": found["matches"], "count": found["count"]}

    @mcp.tool()
    def dana_tool_costs(names: list[str] | None = None) -> dict[str, Any]:
        """Return conservative latency/token/cpu cost metadata used by the planner."""
        tools, _ = _catalog(mcp)
        selected = set(names or [t.name for t in tools])
        destructive_prefixes = ("write", "edit", "delete", "remove", "stop", "kill", "rollback", "build", "package", "format", "fix", "run_")
        rows = []
        for tool in tools:
            if tool.name not in selected or tool.name.startswith("dana_"):
                continue
            name = tool.name.lower()
            destructive = name.startswith(destructive_prefixes) or any(x in name for x in ("execute", "command", "docker_build", "git_commit"))
            network = any(x in name for x in ("http", "web_", "network", "api", "browser"))
            heavy = any(x in name for x in ("test", "coverage", "benchmark", "analy", "index", "build"))
            rows.append({
                "name": tool.name,
                "token_cost": 2 + estimate_tokens(_compact_description(tool.description)) // 50,
                "latency_class": "high" if heavy else ("medium" if network else "low"),
                "cpu_class": "high" if heavy else "low",
                "network": network,
                "destructive": destructive,
                "cacheable": tool.name in _CACHE_TTLS,
                "parallelizable": not destructive,
            })
        return {"tools": rows, "count": len(rows)}

    def _execution_layers(calls: list[dict[str, Any]]) -> list[list[int]]:
        n = len(calls)
        deps = []
        for i, item in enumerate(calls):
            raw = item.get("depends_on", []) or []
            indices = set()
            for d in raw:
                if isinstance(d, int) and 0 <= d < n and d != i:
                    indices.add(d)
                elif isinstance(d, str):
                    indices.update(j for j, x in enumerate(calls) if x.get("id") == d and j != i)
            deps.append(indices)
        layers: list[list[int]] = []
        done: set[int] = set()
        remaining = set(range(n))
        while remaining:
            ready = sorted(i for i in remaining if deps[i] <= done)
            if not ready:
                raise ValueError("Tool plan contains a dependency cycle or invalid dependency")
            layers.append(ready)
            done.update(ready)
            remaining.difference_update(ready)
        return layers

    @mcp.tool()
    async def dana_plan_execute(calls: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute a dependency-aware plan. Independent safe calls run concurrently; mutating calls run alone."""
        if not calls:
            return {"layers": [], "results": []}
        if len(calls) > 16:
            raise ValueError("A plan may contain at most 16 calls")
        layers = _execution_layers(calls)
        results: list[dict[str, Any] | None] = [None] * len(calls)

        async def execute(i: int) -> dict[str, Any]:
            item = calls[i]
            name = str(item.get("name", "")).strip()
            args = item.get("arguments") or {}
            if not name or name.startswith("dana_") or name not in mcp._tool_manager._tools:
                return {"id": item.get("id", i), "name": name, "ok": False, "error": "Unknown or unsupported tool"}
            try:
                started = time.perf_counter()
                value = await raw_call_tool(name, args, context=None, convert_result=False)
                value = optimize_result(value)
                duration = (time.perf_counter() - started) * 1000
                conn = _db()
                conn.execute(
                    "INSERT INTO calls(ts,tool,input_tokens,output_tokens,duration_ms,cached,batch,success) VALUES(?,?,?,?,?,?,?,?)",
                    (time.time(), name, estimate_tokens(args), estimate_tokens(value), duration, 0, 1, 1),
                )
                conn.commit(); conn.close()
                return {"id": item.get("id", i), "name": name, "ok": True, "result": value, "duration_ms": round(duration, 2)}
            except (ValueError, RuntimeError, OSError) as exc:
                return {"id": item.get("id", i), "name": name, "ok": False, "error": str(exc)}

        for layer in layers:
            names = [str(calls[i].get("name", "")) for i in layer]
            cost_rows = dana_tool_costs(names)["tools"]
            parallel = len(layer) > 1 and len(cost_rows) == len(layer) and all(x.get("parallelizable", False) for x in cost_rows)
            if parallel:
                values = await asyncio.gather(*(execute(i) for i in layer))
            else:
                values = []
                for i in layer:
                    values.append(await execute(i))
            for i, value in zip(layer, values):
                results[i] = value
        return {"layers": layers, "parallel_layers": [x for x in layers if len(x) > 1], "results": results}

    @mcp.tool()
    def dana_result_delta(previous: Any, current: Any) -> dict[str, Any]:
        """Return only structural changes between two results to avoid retransmitting unchanged data."""
        if previous == current:
            return {"changed": False, "delta": None, "saved_tokens_est": estimate_tokens(current)}
        if isinstance(previous, dict) and isinstance(current, dict):
            changed = {k: current[k] for k in current if previous.get(k) != current[k]}
            removed = [k for k in previous if k not in current]
            return {"changed": True, "delta": {"changed": changed, "removed": removed}, "saved_tokens_est": max(0, estimate_tokens(current) - estimate_tokens(changed))}
        return {"changed": True, "delta": current, "saved_tokens_est": 0}

    @mcp.tool()
    def dana_optimization_controller(context_tokens: int = 0, tool_count: int = 0, history_tokens: int = 0, result_tokens: int = 0, tool_calls: int = 0) -> dict[str, Any]:
        """Choose optimization policies from observed request complexity and context pressure."""
        total = max(0, context_tokens)
        if total == 0:
            total = history_tokens + result_tokens
        level = "normal"
        if total > 24000 or tool_count > 20 or tool_calls > 6:
            level = "aggressive"
        elif total > 10000 or tool_count > 8 or tool_calls > 3:
            level = "balanced"
        return {
            "level": level,
            "actions": [
                "use_fast_path" if level != "normal" else "prefer_fast_path",
                "use_progressive_tools",
                "compact_history" if history_tokens > 4000 or level == "aggressive" else "retain_relevant_history",
                "paginate_large_results" if result_tokens > 3000 or level == "aggressive" else "return_compact_results",
                "parallelize_independent_safe_tools" if tool_calls > 1 else "single_tool_path",
                "use_cache_for_read_only_tools",
            ],
            "recommended_budget_tokens": 8000 if level == "aggressive" else (16000 if level == "balanced" else 32000),
        }

    # Keep the complete registry internally, but expose only the progressive
    # entry points to MCP clients. This is the key context/token optimization.
    manager = mcp._tool_manager
    original_list_tools = manager.list_tools
    original_visible = set(_visible_names(mcp))
    progressive_enabled = os.getenv(
        "DANA_PROGRESSIVE_TOOLS", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}

    def optimized_list_tools() -> list[Any]:
        all_tools = original_list_tools()
        if not progressive_enabled:
            return all_tools
        return [tool for tool in all_tools if tool.name in original_visible]

    manager.list_tools = optimized_list_tools

    # Keep a deterministic, compact order in the underlying registry too.
    ordered = dict(sorted(manager._tools.items(), key=lambda item: item[0]))
    manager._tools.clear()
    manager._tools.update(ordered)
