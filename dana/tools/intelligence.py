from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .engineering import _files, _root, _text

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".php", ".go", ".rs", ".java"}


def _definitions(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in _files(root):
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                result.append(
                    {
                        "name": node.name,
                        "kind": type(node).__name__,
                        "path": str(path.relative_to(root)),
                        "line": node.lineno,
                    }
                )
    return result


def _imports(root: Path) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for path in _files(root):
        if path.suffix != ".py":
            continue
        names: list[str] = []
        try:
            tree = ast.parse(_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        graph[str(path.relative_to(root))] = sorted(set(names))
    return graph


def _references(root: Path, name: str) -> list[dict[str, Any]]:
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    hits = []
    for path in _files(root):
        if path.suffix not in CODE_EXT:
            continue
        for line_no, line in enumerate(_text(path).splitlines(), 1):
            if pattern.search(line):
                hits.append(
                    {
                        "path": str(path.relative_to(root)),
                        "line": line_no,
                        "text": line.strip()[:240],
                    }
                )
    return hits


def _tests_for(root: Path, target: str) -> list[str]:
    tokens = [
        part.lower()
        for part in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", target)
        if len(part) > 2
    ]
    matches = []
    for path in _files(root):
        rel = str(path.relative_to(root))
        if "test" not in path.name.lower() and "/tests/" not in f"/{rel}":
            continue
        text = _text(path).lower()
        if any(token in text or token in path.name.lower() for token in tokens):
            matches.append(rel)
    return sorted(set(matches))[:100]


def register_intelligence_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_map_repository(path: str = ".") -> dict[str, Any]:
        """Build a repository intelligence map: languages, modules, entry points and import graph."""
        root = _root(path)
        files = list(_files(root))
        languages = defaultdict(int)
        for item in files:
            languages[item.suffix or "[no extension]"] += 1
        entries = []
        for item in files:
            if item.name in {
                "main.py",
                "app.py",
                "server.py",
                "manage.py",
                "index.ts",
                "index.js",
            }:
                entries.append(str(item.relative_to(root)))
        return {
            "root": str(root),
            "files": len(files),
            "languages": dict(sorted(languages.items(), key=lambda item: -item[1])),
            "entry_points": entries,
            "definitions": _definitions(root)[:500],
            "import_graph": _imports(root),
        }

    @mcp.tool()
    def dana_trace_symbol(path: str, symbol: str) -> dict[str, Any]:
        """Trace definitions and references for a symbol across the repository."""
        root = _root(path)
        definitions = [item for item in _definitions(root) if item["name"] == symbol]
        return {
            "symbol": symbol,
            "definitions": definitions,
            "references": _references(root, symbol),
        }

    @mcp.tool()
    def dana_analyze_change_impact(
        path: str, target: str, change: str = ""
    ) -> dict[str, Any]:
        """Estimate affected code, tests and regression risk before making a change."""
        root = _root(path)
        target_path = root / target if root.is_dir() else root
        symbols = []
        if target_path.exists() and target_path.suffix == ".py":
            try:
                tree = ast.parse(_text(target_path))
                symbols = [
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
                ]
            except SyntaxError:
                pass
        affected = []
        for symbol in symbols[:30]:
            affected.extend(_references(root, symbol))
        unique = {(item["path"], item["line"]): item for item in affected}
        affected_files = sorted({item["path"] for item in unique.values()})
        tests = _tests_for(root, target + " " + change + " " + " ".join(symbols))
        risk = (
            "high"
            if len(affected_files) > 20
            else "medium"
            if len(affected_files) > 5
            else "low"
        )
        return {
            "target": target,
            "change": change,
            "symbols": symbols,
            "affected_files": affected_files,
            "reference_count": len(unique),
            "related_tests": tests,
            "risk": risk,
            "recommended_validation": [
                "targeted tests",
                "static checks",
                "integration test for changed flow",
                "review public API compatibility",
            ],
        }

    @mcp.tool()
    def dana_debug_issue(path: str, error: str, logs: str = "") -> dict[str, Any]:
        """Autonomous-debug assistant: extract evidence, likely symbols and a minimal debug plan without changing code."""
        root = _root(path)
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", error + " " + logs)
        ranked = []
        for token in dict.fromkeys(tokens):
            refs = _references(root, token)
            if refs:
                ranked.append(
                    {"token": token, "references": refs[:20], "count": len(refs)}
                )
        ranked.sort(key=lambda item: -item["count"])
        return {
            "error": error,
            "evidence": logs[-4000:],
            "candidates": ranked[:20],
            "workflow": [
                "reproduce",
                "collect stacktrace/logs",
                "trace candidate symbols",
                "identify smallest root-cause hypothesis",
                "apply minimal fix",
                "run targeted tests",
                "run regression checks",
            ],
            "next_action": "inspect highest-ranked candidate before changing unrelated code",
        }

    @mcp.tool()
    def dana_test_intelligence(
        path: str = ".", changed_target: str = ""
    ) -> dict[str, Any]:
        """Find relevant tests and suggest missing test categories for a change."""
        root = _root(path)
        tests = [
            str(item.relative_to(root))
            for item in _files(root)
            if "test" in item.name.lower()
        ]
        relevant = _tests_for(root, changed_target) if changed_target else tests
        return {
            "test_files": tests[:300],
            "relevant_tests": relevant,
            "missing_test_categories": [
                "happy path",
                "invalid input",
                "boundary values",
                "error handling",
                "regression of changed public behavior",
            ],
            "recommended_order": [
                "run relevant tests",
                "add missing focused tests",
                "run full suite",
            ],
        }

    @mcp.tool()
    def dana_api_intelligence(path: str = ".") -> dict[str, Any]:
        """Discover likely API routes, HTTP handlers and contract-related files."""
        root = _root(path)
        patterns = re.compile(
            r"@(app|router)\.(get|post|put|delete|patch)|Route\(|path\("
        )
        hits = []
        for item in _files(root):
            if item.suffix not in CODE_EXT:
                continue
            for line_no, line in enumerate(_text(item).splitlines(), 1):
                if patterns.search(line):
                    hits.append(
                        {
                            "path": str(item.relative_to(root)),
                            "line": line_no,
                            "route": line.strip()[:300],
                        }
                    )
        return {
            "routes": hits[:500],
            "count": len(hits),
            "contract_checks": [
                "request validation",
                "response compatibility",
                "auth requirements",
                "error contract",
                "breaking-change review",
            ],
        }

    @mcp.tool()
    def dana_security_review(path: str = ".") -> dict[str, Any]:
        """Run a lightweight security review for secrets and risky patterns; findings are review evidence, not exploitation."""
        root = _root(path)
        checks = {
            "possible_secret": re.compile(
                r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}"
            ),
            "sql_interpolation": re.compile(
                r"(?i)(select|insert|update|delete).*(%|f['\"]|\.format\()"
            ),
            "dangerous_shell": re.compile(r"subprocess\.(run|Popen).*shell\s*=\s*True"),
        }
        findings = []
        for item in _files(root):
            if item.suffix not in CODE_EXT and item.name != ".env":
                continue
            for line_no, line in enumerate(_text(item).splitlines(), 1):
                for kind, pattern in checks.items():
                    if pattern.search(line):
                        findings.append(
                            {
                                "kind": kind,
                                "path": str(item.relative_to(root)),
                                "line": line_no,
                                "evidence": line.strip()[:240],
                            }
                        )
        return {
            "findings": findings[:300],
            "count": len(findings),
            "review_checklist": [
                "authentication",
                "authorization",
                "input validation",
                "path handling",
                "secrets",
                "dependency security",
                "logging of sensitive data",
            ],
        }
