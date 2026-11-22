"""Proxy Godot Editor MCP tools into Dana's own FastMCP registry.

Forwards to SuperMCP (which owns godot-editor-mcp + WS bridge on 9080).
Uses a single long-lived SSE session; SuperMCP 0.1.8 crashes on concurrent
SSE connects ("Already connected to a transport"), so we never open a second
one while the first is alive.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

_DEFAULT_SUPERMCP = "http://127.0.0.1:3006"
_SESSION_LOCK = threading.RLock()
_SESSION: dict[str, Any] = {
    "endpoint": None,
    "events": None,
    "thread": None,
    "req_id": 100,
    "alive": False,
}


def _supermcp_base() -> str:
    return (os.environ.get("DANA_SUPERMCP_URL") or _DEFAULT_SUPERMCP).rstrip("/")


def _reset_session() -> None:
    _SESSION["endpoint"] = None
    _SESSION["events"] = None
    _SESSION["thread"] = None
    _SESSION["alive"] = False


def _post(ep: str, msg: dict[str, Any], timeout: float = 30.0) -> None:
    body = json.dumps(msg).encode("utf-8")
    req = urllib.request.Request(
        ep,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read(64)


def _ensure_session(timeout: float = 15.0) -> tuple[str, "queue.Queue[str]"]:
    with _SESSION_LOCK:
        th = _SESSION.get("thread")
        if (
            _SESSION.get("alive")
            and _SESSION.get("endpoint")
            and _SESSION.get("events") is not None
            and th is not None
            and th.is_alive()
        ):
            return _SESSION["endpoint"], _SESSION["events"]

        _reset_session()
        events: queue.Queue[str] = queue.Queue()
        endpoint_holder: dict[str, str | None] = {"url": None}
        err_holder: dict[str, str | None] = {"err": None}

        def reader() -> None:
            try:
                # no read timeout — keep SSE open for the process lifetime
                req = urllib.request.Request(
                    f"{_supermcp_base()}/sse",
                    headers={"Accept": "text/event-stream"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    # after headers, switch to blocking unlimited reads
                    resp.fp.raw._sock.settimeout(None)  # type: ignore[attr-defined]
                    buf = b""
                    while True:
                        chunk = resp.read(1)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            text = line.decode("utf-8", "replace").rstrip("\r")
                            if text.startswith("data:"):
                                data = text[5:].strip()
                                events.put(data)
                                if data.startswith("/") or data.startswith("http"):
                                    endpoint_holder["url"] = data
            except Exception as exc:  # noqa: BLE001
                err_holder["err"] = f"{type(exc).__name__}: {exc}"
                events.put(f"ERR:{err_holder['err']}")
            finally:
                _SESSION["alive"] = False

        th = threading.Thread(target=reader, daemon=True, name="dana-godot-supermcp-sse")
        th.start()
        deadline = time.time() + timeout
        while time.time() < deadline and not endpoint_holder["url"] and not err_holder["err"]:
            time.sleep(0.05)
        if err_holder["err"]:
            _reset_session()
            raise RuntimeError(f"SuperMCP SSE failed: {err_holder['err']}")
        ep = endpoint_holder["url"]
        if not ep:
            _reset_session()
            raise RuntimeError(
                f"SuperMCP SSE endpoint not available at {_supermcp_base()}/sse. "
                "Is SuperMCP running on port 3006?"
            )
        if ep.startswith("/"):
            ep = f"{_supermcp_base()}{ep}"

        _post(
            ep,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "dana-godot-proxy", "version": "1.1"},
                },
            },
        )
        end = time.time() + 8
        while time.time() < end:
            try:
                data = events.get(timeout=0.4)
            except queue.Empty:
                continue
            if data.startswith("/") or data.startswith("http"):
                continue
            try:
                j = json.loads(data)
            except json.JSONDecodeError:
                continue
            if j.get("id") == 1:
                break
        _post(ep, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        _SESSION["endpoint"] = ep
        _SESSION["events"] = events
        _SESSION["thread"] = th
        _SESSION["alive"] = True
        _SESSION["req_id"] = 100
        return ep, events


def _call_supermcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    arguments = arguments or {}
    with _SESSION_LOCK:
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                ep, events = _ensure_session()
                _SESSION["req_id"] = int(_SESSION.get("req_id") or 100) + 1
                rid = _SESSION["req_id"]
                # drain stale events
                while True:
                    try:
                        events.get_nowait()
                    except queue.Empty:
                        break
                _post(
                    ep,
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments},
                    },
                    timeout=60.0,
                )
                deadline = time.time() + 45
                while time.time() < deadline:
                    try:
                        data = events.get(timeout=1.0)
                    except queue.Empty:
                        if not _SESSION.get("alive"):
                            raise RuntimeError("SuperMCP SSE session died mid-call")
                        continue
                    if data.startswith("ERR:"):
                        _reset_session()
                        raise RuntimeError(data[4:])
                    if data.startswith("/") or data.startswith("http"):
                        continue
                    try:
                        j = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if j.get("id") != rid:
                        continue
                    if "error" in j:
                        err = j["error"]
                        raise RuntimeError(json.dumps(err, ensure_ascii=False))
                    result = j.get("result") or {}
                    # unwrap MCP content
                    content = result.get("content") if isinstance(result, dict) else None
                    if content and isinstance(content, list) and content:
                        texts = [c.get("text") for c in content if isinstance(c, dict) and c.get("text")]
                        if len(texts) == 1:
                            try:
                                return json.loads(texts[0])
                            except (json.JSONDecodeError, TypeError):
                                return texts[0]
                        if texts:
                            return texts
                    if isinstance(result, dict) and "structuredContent" in result:
                        return result["structuredContent"]
                    return result
                raise TimeoutError(f"Timeout waiting for SuperMCP tool {tool_name}")
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                _reset_session()
                time.sleep(0.4 * (attempt + 1))
        raise RuntimeError(f"Godot proxy failed after retries: {last_err}")


def _resolve_tool_name(name: str) -> str:
    if name.startswith("Godot."):
        return name
    if name.startswith("godot."):
        return "Godot." + name[len("godot."):]
    if name.startswith("Godot__"):
        return "Godot." + name[len("Godot__"):]
    if name.startswith("godot_"):
        return f"Godot.{name}"
    return f"Godot.godot_{name}"


def register_godot_proxy_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def godot_health_check() -> Any:
        """Check live Godot Editor MCP bridge status (via SuperMCP)."""
        return _call_supermcp_tool("Godot.godot_health_check")

    @mcp.tool()
    def godot_project_info() -> Any:
        """Read live project info from the connected Godot Editor (TheLastHour etc.)."""
        return _call_supermcp_tool("Godot.godot_inspection_get_project_info")

    @mcp.tool()
    def godot_list_scenes() -> Any:
        """List scenes known to the connected Godot Editor project."""
        return _call_supermcp_tool("Godot.godot_inspection_list_scenes")

    @mcp.tool()
    def godot_get_active_scene() -> Any:
        """Get the currently active scene in the Godot Editor (read-only)."""
        return _call_supermcp_tool("Godot.godot_inspection_get_active_scene")

    @mcp.tool()
    def godot_get_scene_tree() -> Any:
        """Get the live scene tree from the active scene in Godot Editor."""
        return _call_supermcp_tool("Godot.godot_inspection_get_scene_tree")

    @mcp.tool()
    def godot_get_selected_node() -> Any:
        """Get the currently selected node in the Godot Editor."""
        return _call_supermcp_tool("Godot.godot_inspection_get_selected_node")

    @mcp.tool()
    def godot_list_toolsets() -> Any:
        """List Godot MCP toolsets (inspection is on by default; others can be enabled)."""
        return _call_supermcp_tool("Godot.godot_list_toolsets")

    @mcp.tool()
    def godot_enable_toolset(name: str) -> Any:
        """Enable a Godot MCP toolset (e.g. scene_edit, scripts, runtime)."""
        return _call_supermcp_tool("Godot.godot_enable_toolset", {"name": name})

    @mcp.tool()
    def godot_list_remote_tools() -> Any:
        """List all Godot tools currently exposed by SuperMCP (live)."""
        with _SESSION_LOCK:
            ep, events = _ensure_session()
            _SESSION["req_id"] = int(_SESSION.get("req_id") or 100) + 1
            rid = _SESSION["req_id"]
            while True:
                try:
                    events.get_nowait()
                except queue.Empty:
                    break
            _post(ep, {"jsonrpc": "2.0", "id": rid, "method": "tools/list", "params": {}})
            deadline = time.time() + 20
            while time.time() < deadline:
                try:
                    data = events.get(timeout=1.0)
                except queue.Empty:
                    continue
                if data.startswith("/") or data.startswith("http") or data.startswith("ERR:"):
                    continue
                try:
                    j = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if j.get("id") != rid:
                    continue
                tools = (j.get("result") or {}).get("tools") or []
                godot = [
                    {"name": t.get("name"), "description": (t.get("description") or "")[:160]}
                    for t in tools
                    if isinstance(t, dict) and "godot" in (t.get("name") or "").lower()
                ]
                return {"count": len(godot), "tools": godot, "via": _supermcp_base()}
            return {"count": 0, "tools": [], "via": _supermcp_base(), "error": "timeout"}

    @mcp.tool()
    def godot_call(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call any Godot MCP tool by short or remote name (e.g. godot_health_check or Godot.godot_health_check)."""
        return _call_supermcp_tool(_resolve_tool_name(tool_name), arguments)
