from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

_TASKS: dict[str, threading.Timer] = {}


def _path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _run(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 120,
    shell: bool = False,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(_path(cwd)) if cwd else None,
            shell=shell,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-20000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": -1,
            "stdout": (exc.stdout or "")[-20000:],
            "stderr": "timeout",
        }


def register_agent_tools(mcp: FastMCP) -> None:
    # Files and directories
    @mcp.tool()
    def read_file(path: str) -> str:
        """Read a UTF-8 text file."""
        return _path(path).read_text(encoding="utf-8")

    @mcp.tool()
    def write_file(path: str, content: str, overwrite: bool = True) -> str:
        """Create or replace a text file."""
        target = _path(path)
        if target.exists() and not overwrite:
            raise ValueError("File already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    @mcp.tool()
    def edit_file(
        path: str, old: str, new: str, replace_all: bool = False
    ) -> dict[str, Any]:
        """Replace exact text inside an existing file."""
        target = _path(path)
        text = target.read_text(encoding="utf-8")
        count = text.count(old)
        if not count:
            raise ValueError("Target text not found")
        target.write_text(
            text.replace(old, new) if replace_all else text.replace(old, new, 1),
            encoding="utf-8",
        )
        return {"path": str(target), "matches": count}

    @mcp.tool()
    def delete_path(path: str, recursive: bool = False) -> str:
        """Delete a file or directory."""
        target = _path(path)
        if target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
        else:
            target.unlink()
        return str(target)

    @mcp.tool()
    def search_code(
        path: str, pattern: str, file_glob: str = "*"
    ) -> list[dict[str, Any]]:
        """Search source files using a regular expression."""
        root = _path(path)
        regex = re.compile(pattern)
        results = []
        for file in root.rglob(file_glob):
            if not file.is_file() or any(
                part in {".git", ".venv", "node_modules", "__pycache__"}
                for part in file.parts
            ):
                continue
            try:
                for i, line in enumerate(
                    file.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                ):
                    if regex.search(line):
                        results.append(
                            {"path": str(file), "line": i, "text": line[:500]}
                        )
                        if len(results) >= 500:
                            return results
            except OSError:
                pass
        return results

    # Shell, processes, runtimes and logs
    @mcp.tool()
    def run_command(
        command: str, cwd: str | None = None, timeout: int = 120
    ) -> dict[str, Any]:
        """Run a shell command for coding, tests, builds and diagnostics."""
        return _run(command, cwd, timeout, shell=True)

    @mcp.tool()
    def run_process(
        command: list[str], cwd: str | None = None, timeout: int = 120
    ) -> dict[str, Any]:
        """Run a process without a shell."""
        return _run(command, cwd, timeout)

    @mcp.tool()
    def process_list() -> list[dict[str, str]]:
        """List running processes."""
        if os.name == "nt":
            out = _run(["tasklist", "/FO", "CSV"])
        else:
            out = _run(["ps", "-eo", "pid,ppid,comm,args"])
        return [{"output": out.get("stdout", ""), "stderr": out.get("stderr", "")}]

    @mcp.tool()
    def process_stop(pid: int) -> dict[str, Any]:
        """Stop a process by PID."""
        return _run(
            ["taskkill", "/PID", str(pid), "/F"]
            if os.name == "nt"
            else ["kill", "-TERM", str(pid)]
        )

    @mcp.tool()
    def read_log(path: str, lines: int = 200) -> str:
        """Read the last lines of a log file."""
        data = _path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(data[-lines:])

    @mcp.tool()
    def debug_trace(
        command: str, cwd: str | None = None, timeout: int = 120
    ) -> dict[str, Any]:
        """Execute a diagnostic command and return stdout/stderr/exit code."""
        return _run(command, cwd, timeout, shell=True)

    # Git and code quality
    @mcp.tool()
    def git(command: list[str], cwd: str = ".", timeout: int = 120) -> dict[str, Any]:
        """Run a Git subcommand, e.g. ['status','--short'] or ['commit','-m','message']."""
        return _run(["git", *command], cwd, timeout)

    @mcp.tool()
    def run_tests(
        command: str = "pytest -q", cwd: str = ".", timeout: int = 300
    ) -> dict[str, Any]:
        """Run a project's test command."""
        return _run(command, cwd, timeout, shell=True)

    @mcp.tool()
    def lint_or_format(
        command: str, cwd: str = ".", timeout: int = 300
    ) -> dict[str, Any]:
        """Run linting or formatting commands."""
        return _run(command, cwd, timeout, shell=True)

    @mcp.tool()
    def package_manager(
        command: str, cwd: str = ".", timeout: int = 300
    ) -> dict[str, Any]:
        """Run package-manager commands such as pip, npm or composer."""
        return _run(command, cwd, timeout, shell=True)

    @mcp.tool()
    def build_project(
        command: str, cwd: str = ".", timeout: int = 300
    ) -> dict[str, Any]:
        """Run a project build command."""
        return _run(command, cwd, timeout, shell=True)

    # Environment and HTTP
    @mcp.tool()
    def environment(
        action: str, key: str | None = None, value: str | None = None
    ) -> dict[str, Any]:
        """Get/list/set/unset environment variables for the Dana process."""
        action = action.lower()
        if action == "get":
            return {"value": os.getenv(key or "")}
        if action == "list":
            return dict(os.environ)
        if action == "set" and key:
            os.environ[key] = value or ""
            return {"ok": True}
        if action == "unset" and key:
            os.environ.pop(key, None)
            return {"ok": True}
        raise ValueError("Use get, list, set or unset")

    @mcp.tool()
    def http_request(
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Send an HTTP request for API testing."""
        req = urllib.request.Request(
            url,
            data=body.encode() if body is not None else None,
            method=method.upper(),
            headers=headers or {},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response.read().decode("utf-8", "replace")[:50000],
                }
        except Exception as exc:
            return {"error": str(exc)}

    # Database
    @mcp.tool()
    def sqlite_query(
        database: str, query: str, params: list[Any] | None = None
    ) -> dict[str, Any]:
        """Execute a SQLite query."""
        with sqlite3.connect(str(_path(database))) as conn:
            cur = conn.execute(query, params or [])
            if cur.description:
                columns = [x[0] for x in cur.description]
                return {
                    "columns": columns,
                    "rows": [dict(zip(columns, row)) for row in cur.fetchall()],
                }
            conn.commit()
            return {"rowcount": cur.rowcount}

    # Docker, network and system
    @mcp.tool()
    def docker(
        command: list[str], cwd: str = ".", timeout: int = 300
    ) -> dict[str, Any]:
        """Run a Docker command, e.g. ['ps'] or ['compose','up','-d']."""
        return _run(["docker", *command], cwd, timeout)

    @mcp.tool()
    def network_check(
        host: str, port: int | None = None, timeout: int = 5
    ) -> dict[str, Any]:
        """Resolve a host and optionally test a TCP port."""
        result: dict[str, Any] = {
            "host": host,
            "addresses": sorted({x[4][0] for x in socket.getaddrinfo(host, None)}),
        }
        if port is not None:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    result["port_open"] = True
            except OSError as exc:
                result["port_open"] = False
                result["error"] = str(exc)
        return result

    @mcp.tool()
    def system_details() -> dict[str, Any]:
        """Return host OS, Python, CPU and runtime details."""
        return {
            "os": platform.platform(),
            "hostname": socket.gethostname(),
            "python": sys.version,
            "cpu_count": os.cpu_count(),
            "cwd": os.getcwd(),
        }

    # Scheduling
    @mcp.tool()
    def schedule_command(
        task_id: str, command: str, delay_seconds: int, cwd: str | None = None
    ) -> dict[str, Any]:
        """Schedule a one-shot command in the running Dana process."""
        if task_id in _TASKS:
            _TASKS[task_id].cancel()
        timer = threading.Timer(delay_seconds, lambda: _run(command, cwd, shell=True))
        timer.daemon = True
        _TASKS[task_id] = timer
        timer.start()
        return {"task_id": task_id, "delay_seconds": delay_seconds}

    @mcp.tool()
    def cancel_scheduled_task(task_id: str) -> bool:
        """Cancel a scheduled command."""
        timer = _TASKS.pop(task_id, None)
        if not timer:
            return False
        timer.cancel()
        return True

    # Browser automation (optional Playwright dependency)
    @mcp.tool()
    def browser_automation(
        url: str,
        action: str = "text",
        selector: str | None = None,
        value: str | None = None,
    ) -> dict[str, Any]:
        """Automate a browser with Playwright. Actions: text, title, click, fill, screenshot."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "error": "Playwright is not installed. Install playwright and run 'playwright install'."
            }
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            if action == "title":
                result: Any = page.title()
            elif action == "text":
                result = page.locator(selector or "body").inner_text()
            elif action == "click":
                page.locator(selector or "").click()
                result = {"url": page.url}
            elif action == "fill":
                page.locator(selector or "").fill(value or "")
                result = True
            elif action == "screenshot":
                path = value or "dana-browser.png"
                page.screenshot(path=path)
                result = str(_path(path))
            else:
                raise ValueError("Unknown action")
            browser.close()
            return {"result": result}
