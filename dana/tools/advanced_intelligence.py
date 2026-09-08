from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .engineering import _files, _root, _text
from .intelligence import CODE_EXT, _imports, _references

_CACHE: dict[str, dict[str, Any]] = {}


def _cache_key(root: Path, name: str, payload: str = "") -> str:
    stamp = "|".join(f"{p.relative_to(root)}:{p.stat().st_mtime_ns}" for p in list(_files(root))[:1000])
    return hashlib.sha256(f"{root}|{name}|{payload}|{stamp}".encode()).hexdigest()


def _cached(root: Path, name: str, payload: str, builder):
    key = _cache_key(root, name, payload)
    if key not in _CACHE:
        _CACHE[key] = builder()
        if len(_CACHE) > 32:
            _CACHE.pop(next(iter(_CACHE)))
    return _CACHE[key]


def _python_calls(root: Path) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for path in _files(root):
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(_text(path))
        except SyntaxError:
            continue
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name): calls.add(func.id)
                elif isinstance(func, ast.Attribute): calls.add(func.attr)
        graph[str(path.relative_to(root))] = sorted(calls)
    return graph


def _manifest_files(root: Path) -> list[str]:
    names = {"pyproject.toml", "requirements.txt", "package.json", "composer.json", "go.mod", "Cargo.toml", "docker-compose.yml", "Dockerfile"}
    return [str(p.relative_to(root)) for p in _files(root) if p.name in names]


def _db_patterns(root: Path) -> list[dict[str, Any]]:
    pattern = re.compile(r"(?i)(create table|alter table|create index|select .* from|insert into|update .* set|delete from|execute\(|query\()")
    hits = []
    for path in _files(root):
        if path.suffix not in CODE_EXT and path.suffix != ".sql": continue
        for line, value in enumerate(_text(path).splitlines(), 1):
            if pattern.search(value): hits.append({"path": str(path.relative_to(root)), "line": line, "evidence": value.strip()[:260]})
    return hits


def register_advanced_intelligence_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_database_intelligence(path: str = ".") -> dict[str, Any]:
        """Discover database/schema/query patterns and return compact migration/index review guidance."""
        root = _root(path)
        return _cached(root, "db", "", lambda: {"evidence": _db_patterns(root)[:80], "review": ["indexes for filter/join columns", "migration reversibility", "N+1 risk", "transaction boundaries", "query parameterization"], "risk_rules": ["large table migration without batching", "unbounded query", "string-built SQL"]})

    @mcp.tool()
    def dana_rank_root_causes(path: str, error: str, max_candidates: int = 8) -> dict[str, Any]:
        """Rank likely root causes from error tokens and repository references."""
        root = _root(path); tokens = dict.fromkeys(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", error))
        ranked = []
        for token in tokens:
            refs = _references(root, token)
            if refs:
                score = min(100, len(refs) * 5 + (25 if "error" in token.lower() else 0))
                ranked.append({"candidate": token, "score": score, "evidence": refs[:5]})
        ranked.sort(key=lambda x: -x["score"])
        return {"error": error, "candidates": ranked[:max(1, min(max_candidates, 20))], "method": "repository reference density and error-token evidence"}

    @mcp.tool()
    def dana_predict_regression(path: str, target: str) -> dict[str, Any]:
        """Predict regression surface from imports, calls and textual references."""
        root = _root(path); refs = _references(root, Path(target).stem)
        imports = _imports(root); affected = {r["path"] for r in refs}
        for file, deps in imports.items():
            if Path(target).stem in " ".join(deps): affected.add(file)
        risk = "high" if len(affected) > 15 else "medium" if len(affected) > 4 else "low"
        return {"target": target, "affected": sorted(affected)[:200], "risk": risk, "validation": ["target tests", "API contract tests", "integration smoke test"]}

    @mcp.tool()
    def dana_record_architecture_decision(path: str, decision: str, context: str, alternatives: list[str] | None = None) -> dict[str, Any]:
        """Create a compact Architecture Decision Record payload without modifying the repository."""
        alternatives = alternatives or []
        digest = hashlib.sha256((decision + context + "|".join(alternatives)).encode()).hexdigest()[:12]
        return {"id": f"ADR-{digest}", "decision": decision, "context": context, "alternatives": alternatives, "template": {"status": "proposed", "decision": decision, "consequences": ["document tradeoffs before implementation"], "validation": ["review", "tests", "rollback plan"]}}

    @mcp.tool()
    def dana_cross_repository_intelligence(paths: list[str]) -> dict[str, Any]:
        """Compare multiple repositories using manifests and import-level fingerprints."""
        if not paths: raise ValueError("At least one repository path is required")
        repos = []
        fingerprints = defaultdict(list)
        for raw in paths[:10]:
            root = _root(raw); manifests = _manifest_files(root); imports = _imports(root)
            fp = hashlib.sha256(json.dumps({"m": manifests, "i": imports}, sort_keys=True).encode()).hexdigest()[:16]
            repos.append({"path": str(root), "manifests": manifests, "files": len(list(_files(root))), "fingerprint": fp})
            fingerprints[fp].append(str(root))
        return {"repositories": repos, "identical_fingerprints": [v for v in fingerprints.values() if len(v) > 1], "note": "uses compact metadata; no full source dump"}

    @mcp.tool()
    def dana_execution_sandbox_plan(goal: str, path: str = ".") -> dict[str, Any]:
        """Generate an isolated execution/validation plan without mutating the working repository."""
        root = _root(path)
        return {"goal": goal, "root": str(root), "steps": ["snapshot git state", "use isolated worktree or temporary copy", "install existing dependencies only", "apply minimal change", "run targeted tests", "run health checks", "review diff", "promote only on success"], "safety": ["never overwrite source baseline", "preserve uncommitted changes", "explicit cleanup"]}

    @mcp.tool()
    def dana_visual_architecture_graph(path: str = ".") -> dict[str, Any]:
        """Return compact nodes/edges for a visual architecture graph; caller may render as HTML."""
        root = _root(path); imports = _imports(root); calls = _python_calls(root)
        nodes = sorted(imports)[:50]; edges = []
        for source, deps in imports.items():
            for dep in deps[:30]: edges.append({"from": source, "to": dep, "type": "import"})
        return {"nodes": nodes, "edges": edges[:100], "call_summary": {k: v[:20] for k, v in list(calls.items())[:40]}, "render_hint": "group nodes by directory and collapse external dependencies"}

    @mcp.tool()
    def dana_self_healing_plan(path: str, error: str, max_attempts: int = 3) -> dict[str, Any]:
        """Produce a bounded Diagnose→Fix→Test→Retry plan to avoid infinite autonomous loops."""
        root = _root(path); attempts = max(1, min(max_attempts, 5))
        return {"root": str(root), "error": error, "max_attempts": attempts, "loop": ["diagnose evidence", "rank root causes", "select minimal reversible fix", "run targeted validation", "stop on success or unchanged failure signature"], "stop_conditions": ["attempt limit", "same failure twice", "new unrelated failure", "requires destructive action"], "token_policy": "reuse cached repository map and return references instead of source bodies"}
