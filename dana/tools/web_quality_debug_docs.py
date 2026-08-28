from __future__ import annotations
import ast, json, re, subprocess, sys, time, traceback, urllib.request
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP

def _run(cmd: list[str], cwd: str | None = None, timeout: int = 300) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return {"returncode": p.returncode, "stdout": p.stdout[-30000:], "stderr": p.stderr[-30000:]}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}

def register_web_quality_debug_docs_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def web_fetch(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"status": r.status, "url": r.url, "headers": dict(r.headers), "body": r.read(500000).decode(errors="replace")}

    @mcp.tool()
    def api_request(url: str, method: str = "GET", headers: dict[str, str] | None = None, body: str | None = None) -> dict[str, Any]:
        req = urllib.request.Request(url, data=body.encode() if body is not None else None, headers=headers or {}, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return {"status": r.status, "headers": dict(r.headers), "body": r.read(500000).decode(errors="replace")}
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool()
    def browser_check(url: str) -> dict[str, Any]:
        """Check browser automation availability and validate a target URL."""
        try:
            import playwright  # noqa: F401
            return {"ok": True, "url": url, "playwright": "available"}
        except ImportError:
            return {"ok": False, "url": url, "error": "Playwright is not installed"}

    @mcp.tool()
    def discover_tests(path: str = ".") -> list[str]:
        root = Path(path).resolve()
        return [str(p) for p in root.rglob("test_*.py") if ".venv" not in p.parts and ".git" not in p.parts]

    @mcp.tool()
    def static_analysis(path: str = ".") -> dict[str, Any]:
        root = Path(path).resolve(); issues = []
        for file in root.rglob("*.py"):
            if any(x in file.parts for x in (".venv", ".git", "__pycache__")): continue
            text = file.read_text(errors="replace")
            try: ast.parse(text, filename=str(file))
            except SyntaxError as e: issues.append({"file": str(file), "line": e.lineno, "type": "syntax", "message": e.msg})
            for n, line in enumerate(text.splitlines(), 1):
                if re.search(r"\b(TODO|FIXME|HACK)\b", line): issues.append({"file": str(file), "line": n, "type": "marker", "message": line.strip()})
        return {"count": len(issues), "issues": issues}

    @mcp.tool()
    def coverage(path: str = ".") -> dict[str, Any]:
        return _run([sys.executable, "-m", "pytest", "--cov=.", "--cov-report=term-missing", "-q"], str(Path(path).resolve()))

    @mcp.tool()
    def benchmark(command: list[str], cwd: str | None = None, runs: int = 3) -> dict[str, Any]:
        out = []
        for _ in range(max(1, min(runs, 20))):
            start = time.perf_counter(); result = _run(command, cwd); out.append({"seconds": time.perf_counter()-start, "returncode": result["returncode"]})
        return {"runs": out}

    @mcp.tool()
    def debug_command(command: list[str], cwd: str | None = None) -> dict[str, Any]:
        return _run(command, cwd)

    @mcp.tool()
    def python_diagnostics(path: str) -> dict[str, Any]:
        try:
            compile(Path(path).read_text(), path, "exec"); return {"ok": True}
        except Exception: return {"ok": False, "traceback": traceback.format_exc()}

    @mcp.tool()
    def generate_readme(path: str = ".") -> str:
        root = Path(path).resolve(); files = sorted(p.name for p in root.iterdir() if not p.name.startswith("."))
        return f"# {root.name}\n\n## Project Files\n" + "\n".join(f"- `{x}`" for x in files[:100]) + "\n"

    @mcp.tool()
    def generate_changelog(path: str = ".") -> str:
        r = _run(["git", "log", "--pretty=format:- %h %s", "-30"], str(Path(path).resolve()))
        return "# Changelog\n\n## Recent Changes\n" + (r["stdout"] or "No Git history available.") + "\n"

    @mcp.tool()
    def architecture_summary(path: str = ".") -> dict[str, Any]:
        root = Path(path).resolve(); counts: dict[str, int] = {}
        for f in root.rglob("*"):
            if f.is_file() and not any(x in f.parts for x in (".git", ".venv", "node_modules")):
                counts[f.suffix or "[none]"] = counts.get(f.suffix or "[none]", 0) + 1
        return {"root": str(root), "top_level": sorted(x.name for x in root.iterdir()), "file_types": counts}

    @mcp.tool()
    def generate_project_diagram(path: str = ".") -> str:
        root = Path(path).resolve(); lines = ["graph TD"]
        for item in sorted(root.iterdir()):
            safe = re.sub(r"\W+", "_", item.name); lines.append(f'ROOT --> {safe}["{item.name}"]')
        return "\n".join(lines)

    @mcp.tool()
    def generate_report(title: str, data: dict[str, Any], output: str | None = None) -> str:
        report = f"# {title}\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```\n"
        if output: Path(output).expanduser().resolve().write_text(report)
        return report
