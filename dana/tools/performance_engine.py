from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Awaitable, Callable

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".dana"
DB = STATE / "performance.db"


@dataclass(frozen=True)
class ToolCost:
    latency: str = "normal"
    token: str = "normal"
    cacheable: bool = False
    parallel: bool = True
    destructive: bool = False


COSTS: dict[str, ToolCost] = {
    "read_file": ToolCost("low", "low", True, True, False),
    "list_directory": ToolCost("low", "low", True, True, False),
    "search_code": ToolCost("medium", "medium", True, True, False),
    "git": ToolCost("medium", "low", False, True, False),
    "run_tests": ToolCost("high", "medium", False, False, False),
    "run_command": ToolCost("high", "medium", False, False, True),
    "write_file": ToolCost("medium", "low", False, False, True),
    "edit_file": ToolCost("medium", "low", False, False, True),
    "delete_path": ToolCost("medium", "low", False, False, True),
}

FAST_PATTERNS = [
    (re.compile(r"^\s*(?:git\s+)?status\s*$", re.IGNORECASE), "git"),
    (
        re.compile(
            r"^\s*(?:show\s+)?(?:system|server)\s+(?:info|status|metrics)\s*$",
            re.IGNORECASE,
        ),
        "system_info",
    ),
    (
        re.compile(r"^\s*(?:list|ls)\s+(?:files|directory)\s*$", re.IGNORECASE),
        "list_directory",
    ),
]


def _db() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS index_files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER, symbols TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS semantic_cache(key TEXT PRIMARY KEY, created REAL, expires REAL, query TEXT, payload TEXT)"
    )
    c.commit()
    return c


def _json(v: Any) -> str:
    return json.dumps(
        v, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
    )


def fingerprint(v: Any) -> str:
    return hashlib.sha256(_json(v).encode()).hexdigest()


def classify_complexity(request: str, history_tokens: int = 0) -> dict[str, Any]:
    text = request or ""
    score = min(
        10,
        len(text) // 120
        + len(
            re.findall(
                r"\b(and|then|also|after|before|all|multiple)\b", text, re.IGNORECASE
            )
        ),
    )
    if history_tokens > 12000:
        score += 2
    if any(
        x in text.lower()
        for x in ("refactor", "debug", "implement", "migrate", "architecture")
    ):
        score += 3
    score = min(10, score)
    budget = 4000 if score <= 2 else 12000 if score <= 5 else 32000
    return {
        "score": score,
        "class": "simple" if score <= 2 else "normal" if score <= 5 else "complex",
        "budget_tokens": budget,
    }


def fast_path(request: str) -> dict[str, Any] | None:
    for pattern, tool in FAST_PATTERNS:
        if pattern.match(request or ""):
            return {"tool": tool, "arguments": {}, "reason": "deterministic fast path"}
    return None


def tool_cost(name: str) -> dict[str, Any]:
    c = COSTS.get(name, ToolCost())
    return {
        "latency": c.latency,
        "token": c.token,
        "cacheable": c.cacheable,
        "parallelizable": c.parallel,
        "destructive": c.destructive,
    }


def build_dag(calls: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = []
    for i, call in enumerate(calls):
        name = str(call.get("name", ""))
        deps = list(call.get("depends_on", []))
        if not deps and i and not tool_cost(name)["parallelizable"]:
            deps = [i - 1]
        nodes.append(
            {
                "id": i,
                "name": name,
                "arguments": call.get("arguments") or {},
                "depends_on": deps,
                "cost": tool_cost(name),
            }
        )
    return {"nodes": nodes, "levels": _levels(nodes)}


def _levels(nodes: list[dict[str, Any]]) -> list[list[int]]:
    done: set[int] = set()
    levels: list[list[int]] = []
    while len(done) < len(nodes):
        ready = [
            n["id"]
            for n in nodes
            if n["id"] not in done and set(n["depends_on"]) <= done
        ]
        if not ready:
            raise ValueError("Tool dependency graph contains a cycle")
        levels.append(ready)
        done.update(ready)
    return levels


def delta(previous: Any, current: Any) -> dict[str, Any]:
    if previous == current:
        return {"changed": False, "delta": None}
    if isinstance(previous, dict) and isinstance(current, dict):
        changed = {k: current[k] for k in current if previous.get(k) != current[k]}
        removed = [k for k in previous if k not in current]
        return {
            "changed": True,
            "delta": changed,
            "removed": removed,
            "unchanged": max(0, len(set(previous) & set(current)) - len(changed)),
        }
    if isinstance(previous, list) and isinstance(current, list):
        common = 0
        for a, b in zip(previous, current):
            if a == b:
                common += 1
            else:
                break
        return {"changed": True, "prefix_unchanged": common, "items": current[common:]}
    return {"changed": True, "delta": current}


def extract_symbols(path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(
                {
                    "name": node.name,
                    "kind": type(node).__name__,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                }
            )
    return sorted(out, key=lambda x: x["line"])


def index_project(path: str = ".", max_files: int = 2000) -> dict[str, Any]:
    base = (
        (ROOT / path).resolve()
        if not Path(path).is_absolute()
        else Path(path).resolve()
    )
    c = _db()
    scanned = changed = 0
    for p in base.rglob("*.py"):
        if scanned >= max_files or any(
            part in {".venv", ".git", "__pycache__", ".dana"} for part in p.parts
        ):
            continue
        scanned += 1
        stat = p.stat()
        key = str(p)
        row = c.execute(
            "SELECT mtime,size FROM index_files WHERE path=?", (key,)
        ).fetchone()
        if not row or row != (stat.st_mtime, stat.st_size):
            symbols = extract_symbols(p)
            changed += 1
            c.execute(
                "INSERT OR REPLACE INTO index_files(path,mtime,size,symbols) VALUES(?,?,?,?)",
                (key, stat.st_mtime, stat.st_size, _json(symbols)),
            )
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM index_files").fetchone()[0]
    c.close()
    return {"scanned": scanned, "reindexed": changed, "indexed": total}


def find_symbols(query: str, limit: int = 20) -> list[dict[str, Any]]:
    c = _db()
    rows = c.execute("SELECT path,symbols FROM index_files").fetchall()
    c.close()
    out = []
    q = query.lower()
    for path, raw in rows:
        for s in json.loads(raw):
            if q in s["name"].lower():
                out.append({"path": path, **s})
            if len(out) >= limit:
                return out
    return out


def semantic_get(query: str, ttl: int = 30) -> Any | None:
    c = _db()
    row = c.execute(
        "SELECT expires,payload FROM semantic_cache WHERE key=?",
        (fingerprint(query.lower()),),
    ).fetchone()
    c.close()
    if row and row[0] > time.time():
        return json.loads(row[1])
    return None


def semantic_put(query: str, payload: Any, ttl: int = 30) -> None:
    c = _db()
    c.execute(
        "INSERT OR REPLACE INTO semantic_cache(key,created,expires,query,payload) VALUES(?,?,?,?,?)",
        (
            fingerprint(query.lower()),
            time.time(),
            time.time() + ttl,
            query,
            _json(payload),
        ),
    )
    c.commit()
    c.close()


def plan(request: str, tools: list[str]) -> dict[str, Any]:
    selected = [t for t in tools if t]
    return {
        "request": request,
        "steps": [
            {"id": i, "tool": t, "depends_on": [] if i == 0 else [i - 1]}
            for i, t in enumerate(selected)
        ],
        "fast_path": fast_path(request),
        "complexity": classify_complexity(request),
    }


async def execute_dag(
    calls: list[dict[str, Any]],
    executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
) -> list[dict[str, Any]]:
    dag = build_dag(calls)
    results = {}
    output = []
    for level in dag["levels"]:

        async def run(i: int):
            n = dag["nodes"][i]
            try:
                return i, True, await executor(n["name"], n["arguments"])
            except Exception as exc:
                return i, False, str(exc)

        batch = await asyncio.gather(*(run(i) for i in level))
        for i, ok, value in batch:
            results[i] = value
            output.append(
                {"id": i, "name": dag["nodes"][i]["name"], "ok": ok, "result": value}
            )
    return [next(x for x in output if x["id"] == i) for i in sorted(results)]


def register_performance_tools(mcp: Any) -> None:
    @mcp.tool()
    def dana_fast_path(request: str) -> dict[str, Any]:
        """Resolve deterministic common requests without planning."""
        return {"match": fast_path(request), "matched": fast_path(request) is not None}

    @mcp.tool()
    def dana_classify_request(request: str, history_tokens: int = 0) -> dict[str, Any]:
        """Select an adaptive context budget from request complexity."""
        return classify_complexity(request, history_tokens)

    @mcp.tool()
    def dana_tool_cost(name: str) -> dict[str, Any]:
        """Return execution and token-cost metadata for a capability."""
        return {"name": name, **tool_cost(name)}

    @mcp.tool()
    def dana_plan(request: str, tools: list[str]) -> dict[str, Any]:
        """Build a compact executable plan from selected capabilities."""
        return plan(request, tools)

    @mcp.tool()
    def dana_dependency_graph(calls: list[dict[str, Any]]) -> dict[str, Any]:
        """Build and validate a dependency DAG for tool execution."""
        return build_dag(calls)

    @mcp.tool()
    def dana_result_delta(previous: Any, current: Any) -> dict[str, Any]:
        """Return only changes between two results."""
        return delta(previous, current)

    @mcp.tool()
    def dana_project_index(path: str = ".", max_files: int = 2000) -> dict[str, Any]:
        """Incrementally index Python files and symbols; unchanged files are skipped."""
        return index_project(path, max_files)

    @mcp.tool()
    def dana_symbol_search(query: str, limit: int = 20) -> dict[str, Any]:
        """Retrieve matching symbols instead of entire source files."""
        return {"query": query, "matches": find_symbols(query, max(1, min(limit, 100)))}

    @mcp.tool()
    def dana_semantic_cache(
        query: str, value: Any = None, ttl: int = 30
    ) -> dict[str, Any]:
        """Read or populate a short-lived normalized semantic cache entry."""
        if value is None:
            hit = semantic_get(query, ttl)
            return {"hit": hit is not None, "value": hit}
        semantic_put(query, value, ttl)
        return {"stored": True, "key": fingerprint(query.lower())}

    @mcp.tool()
    def dana_optimization_controller(
        request: str, history_tokens: int = 0
    ) -> dict[str, Any]:
        """Choose fast-path, adaptive budget, caching and execution strategy for a request."""
        complexity = classify_complexity(request, history_tokens)
        fp = fast_path(request)
        return {
            "fast_path": fp,
            "complexity": complexity,
            "strategy": {
                "use_cache": complexity["class"] != "complex",
                "parallel": complexity["class"] != "simple" or bool(fp),
                "history": "relevant-only",
                "results": "delta-when-previous-result-exists",
                "retrieval": "symbol-level-for-code",
            },
        }
