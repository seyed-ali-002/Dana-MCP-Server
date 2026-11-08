#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import threading
import subprocess
from .subprocess_env import clean_subprocess_env
from multiprocessing import current_process
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .config import settings
from .terminal_ui import worker_event, worker_ready
from .reporting import update_report
from .tools import register_tools

import sys as _sys
for _logger_name in (
    "mcp",
    "mcp.server",
    "mcp.server.lowlevel.server",
    "mcp.server.fastmcp",
    "mcp.server.fastmcp.tools.tool_manager",
    "mcp.server.streamable_http_manager",
    "mcp.server.streamable_http",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "httpx",
    "httpcore",
):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.CRITICAL)
    _logger.propagate = False
    _logger.handlers.clear()

_DEFAULT_WORKER_NAMES = [
    "Atlas", "Nova", "Orion", "Vega", "Echo", "Luna", "Pixel", "Nexus", "Iris", "Argo",
    "Cobalt", "Milo", "Astra", "Onyx", "Raven", "Sol", "Kairo", "Zephyr", "Axiom", "Ember",
    "Sage", "Bolt", "Lyra", "Quill", "Phoenix", "Cosmo", "Drift", "Halo", "Indigo", "Juno",
    "Mars", "River", "Storm", "Titan", "Willow", "Zen", "Orbit", "Comet", "Frost", "Dawn",
]

def _worker_names() -> list[str]:
    config = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".dana_workers.json")
    try:
        with open(config, encoding="utf-8") as handle:
            names = json.load(handle).get("workers", [])
        if isinstance(names, list) and names and all(isinstance(n, str) and n.strip() for n in names):
            return names
    except (OSError, ValueError, TypeError):
        pass
    return _DEFAULT_WORKER_NAMES

def _worker_number() -> int:
    configured = os.getenv("DANA_WORKER_NUMBER")
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            pass
    identity = current_process()._identity
    return identity[0] if identity else 1

def _worker_name(number: int) -> str:
    try:
        from .config import settings
        seed = settings.require_auth_token()
    except (AttributeError, RuntimeError, ValueError):
        seed = os.getenv("DANA_AUTH_TOKEN", "dana")
    names = _worker_names()
    if number <= len(names):
        return names[number - 1]
    ranked = sorted(names, key=lambda name: hashlib.sha256(f"{seed}:worker:{name}".encode()).hexdigest())
    return ranked[(number - 1) % len(ranked)]

WORKER_NUMBER = _worker_number()
WORKER_NAME = _worker_name(WORKER_NUMBER)

class WorkerPool:
    def __init__(self, size: int) -> None:
        self.size = size
        self._next = 0
        self._lock = threading.Lock()
        self._slots = [None] * size
        self._active = [0] * size

    def select(self) -> tuple[int, str]:
        with self._lock:
            number = self._next % self.size + 1
            self._next += 1
        return number, _worker_name(number)

    async def run(self, operation: Any) -> tuple[int, str, Any]:
        if self._slots[0] is None:
            async with asyncio.Lock():
                if self._slots[0] is None:
                    self._slots = [asyncio.Semaphore(1) for _ in range(self.size)]
        number, name = self.select()
        slot = self._slots[number - 1]
        assert slot is not None
        async with slot:
            with self._lock:
                self._active[number - 1] += 1
            try:
                return number, name, await operation()
            finally:
                with self._lock:
                    self._active[number - 1] = max(0, self._active[number - 1] - 1)

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = list(self._active)
        return {
            "workers": self.size,
            "active": sum(active),
            "idle": self.size - sum(active),
            "slots": [
                {"number": i + 1, "name": _worker_name(i + 1), "active": value, "idle": value == 0}
                for i, value in enumerate(active)
            ],
        }

WORKER_POOL = WorkerPool(settings.normalized_workers())

def _tailscale_dns_name() -> str:
    configured = os.getenv("DANA_PUBLIC_HOST", "").strip().rstrip(".").lower()
    if configured:
        return configured
    try:
        result = subprocess.run(["tailscale", "status", "--json"], text=True, capture_output=True, check=False, timeout=3, env=clean_subprocess_env())
        if result.returncode == 0:
            payload = json.loads(result.stdout or "{}")
            name = str(payload.get("Self", {}).get("DNSName", "")).strip().rstrip(".").lower()
            if name:
                return name
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return ""

_allowed_hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*", "::1", "[::1]:*"]
_tailscale_host = _tailscale_dns_name()
if settings.public_host:
    _allowed_hosts.extend([settings.public_host.lower(), f"{settings.public_host.lower()}:*"])
if _tailscale_host:
    _allowed_hosts.extend([_tailscale_host, f"{_tailscale_host}:*"])
_allowed_hosts = list(dict.fromkeys(_allowed_hosts))
_allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
if settings.public_host:
    _allowed_origins.append(f"https://{settings.public_host.lower()}")
if _tailscale_host:
    _allowed_origins.append(f"https://{_tailscale_host}")
if settings.allowed_origins:
    _allowed_origins.extend(x.strip() for x in settings.allowed_origins.split(",") if x.strip())

def _dana_server_instructions(max_chars: int = 6000) -> str:
    base = (
        "Dana is a self-hosted MCP server on the user's machine. "
        "Prefer targeted tools over broad shell when possible. "
        "Call dana_skill_guidance or skill_context when specialized skill packs are enabled. "
        "Large tool outputs may be compacted (context-mode); use dana_result_page for cursors."
    )
    try:
        from dana.skills_registry import active_skill_context
        skills = active_skill_context(max_chars=max(400, min(max_chars, 20000)))
    except Exception:
        skills = ""
    if not skills.strip():
        return base
    merged = base + "\n\n# Enabled skill guidance\n" + skills.strip()
    if len(merged) > max_chars + 400:
        merged = merged[: max_chars + 400].rstrip() + "…"
    return merged

_stateless_http = (os.getenv("DANA_STATELESS_HTTP") or "1").strip().lower() not in {
    "0", "false", "no", "off",
}
mcp = FastMCP(
    "Dana",
    instructions=_dana_server_instructions(),
    host="127.0.0.1",
    port=8765,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts,
        allowed_origins=_allowed_origins,
    ),
    stateless_http=_stateless_http,
)
register_tools(mcp)
try:
    from .mcp_result_fix import strip_tool_output_schemas
    strip_tool_output_schemas(mcp)
except Exception:
    pass
try:
    from .file_logging import install_stdio_safe_logging
    install_stdio_safe_logging()
except Exception:
    pass

@mcp.tool()
def dana_worker_status() -> dict[str, Any]:
    """Return live worker-slot capacity for concurrent MCP sessions."""
    return WORKER_POOL.status()

_original_call_tool = mcp._tool_manager.call_tool
_ORCHESTRATION_TOOLS = {"dana_call_tool", "dana_batch_call", "dana_parallel_call", "dana_plan_execute"}

def refresh_skill_instructions(max_chars: int = 8000) -> dict:
    try:
        from dana.skills_registry import active_skill_context, list_skills
        text = active_skill_context(max_chars=max(500, min(max_chars, 40000)))
        listed = list_skills()
        enabled = sum(1 for s in listed.get("skills", []) if s.get("enabled"))
        return {"ok": True, "enabled_skills": enabled, "chars": len(text), "guidance": text}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "guidance": ""}

def _maybe_context_compact(result: Any) -> Any:
    flag = os.getenv("DANA_CONTEXT_MODE", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return result
    if result is None or not isinstance(result, (dict, list, str)):
        return result
    try:
        from dana.tools.context_engine import MAX_RESULT_CHARS, optimize_result
    except Exception:
        return result
    try:
        raw = _token_text(result)
        if len(raw) <= MAX_RESULT_CHARS:
            return result
        optimized = optimize_result(result, MAX_RESULT_CHARS)
        if isinstance(optimized, (dict, list)):
            return {
                "_dana_context_mode": True,
                "note": "Large tool output compacted to protect context. Use dana_result_page for cursors.",
                "original_chars": len(raw),
                "compacted_chars": len(_token_text(optimized)),
                "result": optimized,
            }
        return optimized
    except Exception:
        return result

@mcp.tool()
def dana_skill_guidance(max_chars: int = 8000) -> dict:
    """Return concatenated instructions from enabled Dana skill packs."""
    return refresh_skill_instructions(max_chars)

async def _logged_call_tool(name: str, arguments: dict[str, Any], context: Any = None, convert_result: bool = False) -> Any:
    started = time.perf_counter()
    input_tokens = _estimate_tokens(arguments)
    token_exact = False
    token_source = "estimate"
    success = True
    worker_number = 1
    worker_name = _worker_name(worker_number)
    result: Any = None
    output_tokens = 0
    try:
        async def operation() -> Any:
            return await _original_call_tool(name, arguments, context=context, convert_result=True)

        if name in _ORCHESTRATION_TOOLS:
            result = await operation()
            worker_number, worker_name = 1, "Gateway"
        else:
            worker_number, worker_name, result = await WORKER_POOL.run(operation)

        if not hasattr(result, "content"):
            result = _maybe_context_compact(_json_safe(result) if not hasattr(result, "model_dump") else result)
        try:
            from .mcp_result_fix import ensure_structured
            result = ensure_structured(result, _json_safe)
        except Exception:
            pass

        usage = _reported_usage(result)
        if usage is not None:
            input_tokens, output_tokens = usage
            token_exact = True
            token_source = "provider_reported"
        else:
            output_tokens = _estimate_tokens(result)
        return result
    except Exception as exc:
        success = False
        output_tokens = 0
        try:
            from .mcp_result_fix import error_result
            result = error_result(f"{type(exc).__name__}: {exc}", detail=str(exc))
            return result
        except Exception:
            raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        report_name = name
        if name == "dana_call_tool" and isinstance(arguments, dict) and arguments.get("name"):
            report_name = str(arguments["name"])
        should_log = (name not in _ORCHESTRATION_TOOLS) or (name == "dana_call_tool" and report_name != "dana_call_tool")
        if should_log:
            logged_args = arguments.get("arguments", arguments) if name == "dana_call_tool" and isinstance(arguments, dict) else arguments
            try:
                args_str = json.dumps(_json_safe(logged_args), ensure_ascii=False, indent=2)
            except Exception:
                args_str = str(logged_args)
            res_text = _token_text(result)
            detail = {
                "args": args_str[:2000],
                "result": (res_text[:2000] if success else ""),
                "error": (res_text[:2000] if not success else ""),
            }
            try:
                threading.Thread(
                    target=update_report,
                    args=(report_name, worker_name, worker_number, input_tokens, output_tokens, duration_ms, success, token_exact, token_source, detail),
                    daemon=True,
                ).start()
            except TypeError:
                threading.Thread(
                    target=update_report,
                    args=(report_name, worker_name, worker_number, input_tokens, output_tokens, duration_ms, success, token_exact, token_source),
                    daemon=True,
                ).start()
            try:
                worker_event(worker_name, worker_number, report_name, input_tokens, output_tokens, duration_ms, success)
            except Exception:
                pass

def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(mode="json"))
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return _json_safe(value.dict())
        except Exception:
            pass
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return {"type": getattr(value, "type", "text"), "text": text}
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)

def _token_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump(mode="json")
        except Exception:
            pass
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif hasattr(item, "text") and isinstance(item.text, str):
                    parts.append(item.text)
                else:
                    try:
                        parts.append(json.dumps(_json_safe(item), ensure_ascii=False, separators=(",", ":")))
                    except Exception:
                        parts.append(str(item))
            if parts:
                return "\n".join(parts)
        if "structuredContent" in value and value.get("structuredContent") is not None:
            try:
                return json.dumps(_json_safe(value["structuredContent"]), ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return str(value["structuredContent"])
    if isinstance(value, str):
        return value
    try:
        return json.dumps(_json_safe(value), ensure_ascii=False, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value)

def _estimate_tokens(value: Any) -> int:
    text = _token_text(value)
    if not text:
        return 0
    estimate = max(0, (len(text) + 3) // 4)
    if os.getenv("DANA_EXACT_TOKENIZER", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return estimate
    try:
        import tiktoken  # type: ignore
        encoding_name = os.getenv("DANA_TOKENIZER_ENCODING", "o200k_base")
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return estimate

def _reported_usage(value: Any) -> tuple[int, int] | None:
    candidates: list[Any] = []
    if isinstance(value, dict):
        candidates.extend([value.get("usage"), value.get("_usage"), value.get("token_usage")])
        for key in ("result", "data", "metadata"):
            nested = value.get(key)
            if isinstance(nested, dict):
                candidates.extend([nested.get("usage"), nested.get("_usage"), nested.get("token_usage")])
    for usage in candidates:
        if isinstance(usage, dict):
            inp = usage.get("input_tokens", usage.get("prompt_tokens"))
            out = usage.get("output_tokens", usage.get("completion_tokens"))
            if isinstance(inp, int) and isinstance(out, int):
                return max(0, inp), max(0, out)
    return None

mcp._tool_manager.call_tool = _logged_call_tool
for _worker_number_value in range(1, settings.normalized_workers() + 1):
    worker_ready(_worker_name(_worker_number_value), _worker_number_value)
