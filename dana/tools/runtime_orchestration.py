from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..config import settings
from ..runtime import TaskRuntime, compact_error, parse_plan, task_to_dict, workspace_context
from .tool_catalog import ALIASES, category_for, enrich


def _tools(mcp: FastMCP) -> list[Any]:
    manager = mcp._tool_manager
    return sorted(manager.list_tools(), key=lambda tool: tool.name)


def _description(tool: Any) -> str:
    return (tool.description or "").strip() or "No description provided."


def register_runtime_orchestration_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_list_tools(category: str | None = None, include_schema: bool = False) -> dict[str, Any]:
        """List all registered Dana tools with stable names, categories, descriptions and optional schemas."""
        items = []
        wanted = category.strip().lower() if category else None
        for tool in _tools(mcp):
            item = enrich(tool)
            if wanted and item["category"] != wanted:
                continue
            if not include_schema:
                item.pop("input_schema", None)
            items.append(item)
        return {"count": len(items), "categories": sorted({x["category"] for x in items}), "tools": items}

    @mcp.tool()
    def dana_search_tools(query: str = "", category: str | None = None, cached_only: bool = False, limit: int = 200) -> dict[str, Any]:
        """Search the complete tool catalog. Empty query returns the full catalog; results include a relevance score."""
        needle = query.strip().lower()
        wanted = category.strip().lower() if category else None
        limit = max(1, min(limit, 200))
        results = []
        for tool in _tools(mcp):
            item = enrich(tool)
            if wanted and item["category"] != wanted:
                continue
            haystack = f"{tool.name} {item['category']} {_description(tool)}".lower()
            if cached_only and "cache" not in haystack:
                continue
            if not needle:
                score = 1.0
            else:
                terms = [x for x in re.split(r"\s+", needle) if x]
                score = sum((3 if term == tool.name.lower() else 2 if term in tool.name.lower() else 1) for term in terms if term in haystack)
                if score <= 0:
                    continue
                score = round(score / max(1, len(terms) * 3), 3)
            item.pop("input_schema", None)
            item["relevance"] = score
            results.append(item)
        results.sort(key=lambda x: (-x["relevance"], x["name"]))
        return {"query": query, "category": category, "count": len(results[:limit]), "results": results[:limit], "aliases": ALIASES}

    @mcp.tool()
    def dana_help_tool(name: str) -> dict[str, Any]:
        """Return complete help for one tool, including category, description, schema and usage guidance."""
        target = next((tool for tool in _tools(mcp) if tool.name == name), None)
        if target is None:
            suggestions = dana_search_tools(name, limit=8)["results"]
            raise ValueError(f"Unknown tool '{name}'. Similar tools: {[x['name'] for x in suggestions]}")
        item = enrich(target)
        item["examples"] = [
            f"Call {name} with arguments matching input_schema.",
            "For unfamiliar tools, use dana_search_tools first, then dana_help_tool for the exact schema.",
        ]
        return item

    @mcp.tool()
    def dana_capabilities(full: bool = True) -> dict[str, Any]:
        """Return a complete, categorized capability inventory instead of a truncated visible-tools list."""
        catalog = dana_list_tools(include_schema=False)
        return {"tool_count": catalog["count"], "categories": catalog["categories"], "tools": catalog["tools"] if full else {category: [x["name"] for x in catalog["tools"] if x["category"] == category] for category in catalog["categories"]}}

    @mcp.tool()
    def dana_workspace_context(path: str = ".") -> dict[str, Any]:
        """Set a workspace context snapshot for an agent without changing global process state."""
        return workspace_context(path)

    @mcp.tool()
    def dana_parallel_call(calls: list[dict[str, Any]], fail_fast: bool = False) -> dict[str, Any]:
        """Execute independent Dana tool calls concurrently. Each call has name and optional arguments."""
        if not calls:
            return {"count": 0, "results": []}
        if len(calls) > settings.normalized_workers() * 4:
            raise ValueError(f"At most {settings.normalized_workers() * 4} parallel calls are allowed per batch")

        async def execute() -> dict[str, Any]:
            async def one(index: int, call: dict[str, Any]) -> dict[str, Any]:
                name = str(call.get("name", ""))
                args = call.get("arguments", {})
                if not name or not isinstance(args, dict):
                    return {"index": index, "ok": False, "error": "Each call needs a name and object arguments"}
                try:
                    result = await mcp._tool_manager.call_tool(name, args, convert_result=False)
                    return {"index": index, "name": name, "ok": True, "result": result}
                except Exception as exc:
                    return {"index": index, "name": name, "ok": False, "error": compact_error(exc)}

            futures = [asyncio.create_task(one(i, call)) for i, call in enumerate(calls)]
            results = await asyncio.gather(*futures)
            if fail_fast and any(not item["ok"] for item in results):
                return {"count": len(results), "failed": True, "results": results}
            return {"count": len(results), "failed": any(not item["ok"] for item in results), "results": results}

        return asyncio.run(execute()) if not _inside_event_loop() else {"error": "Use the async MCP execution path; nested synchronous parallel calls are not supported."}

    @mcp.tool()
    def dana_plan_execute(plan: dict[str, Any], fail_fast: bool = False) -> dict[str, Any]:
        """Execute a dependency-aware task DAG. Independent tasks run concurrently; dependent tasks wait for prerequisites."""
        tasks = parse_plan(plan)

        async def execute() -> dict[str, Any]:
            runtime = TaskRuntime(settings.normalized_workers())

            async def runner(task: Any) -> Any:
                tool_name = task.payload.get("tool") or task.payload.get("name")
                arguments = task.payload.get("arguments", task.payload.get("args", {}))
                if not tool_name:
                    # A planning-only node is valid and can be used as a checkpoint.
                    return {"checkpoint": task.name}
                if not isinstance(arguments, dict):
                    raise ValueError(f"Task '{task.id}' arguments must be an object")
                return await mcp._tool_manager.call_tool(str(tool_name), arguments, convert_result=False)

            return await runtime.execute(tasks, runner, fail_fast=fail_fast)

        return asyncio.run(execute()) if not _inside_event_loop() else {"error": "Nested synchronous plan execution is not supported; use individual task calls."}

    @mcp.tool()
    def dana_runtime_health() -> dict[str, Any]:
        """Check orchestration capacity and MCP tool registration health."""
        tools = _tools(mcp)
        names = [tool.name for tool in tools]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        return {
            "ok": not duplicates and bool(names),
            "workers": settings.normalized_workers(),
            "registered_tools": len(names),
            "duplicate_tool_names": duplicates,
            "orchestration": {"parallel_calls": True, "dependency_dag": True, "bounded_concurrency": True},
        }

    @mcp.tool(name="dana_tool_list")
    def dana_tool_list_legacy(category: str | None = None, include_schema: bool = False) -> dict[str, Any]:
        """Backward-compatible alias for dana_list_tools."""
        return dana_list_tools(category=category, include_schema=include_schema)

    @mcp.tool(name="dana_tool_help")
    def dana_tool_help_legacy(name: str) -> dict[str, Any]:
        """Backward-compatible alias for dana_help_tool."""
        return dana_help_tool(name)

    @mcp.tool(name="dana_workspace_snapshot")
    def dana_workspace_snapshot_legacy(path: str = ".") -> dict[str, Any]:
        """Backward-compatible alias for dana_workspace_context."""
        return dana_workspace_context(path)

    @mcp.tool(name="dana_parallel_execute")
    def dana_parallel_execute_legacy(calls: list[dict[str, Any]], fail_fast: bool = False) -> dict[str, Any]:
        """Backward-compatible alias for dana_parallel_call."""
        return dana_parallel_call(calls, fail_fast=fail_fast)

    @mcp.tool(name="dana_runtime_healthcheck")
    def dana_runtime_healthcheck_legacy() -> dict[str, Any]:
        """Backward-compatible alias for dana_runtime_health."""
        return dana_runtime_health()


def _inside_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True
