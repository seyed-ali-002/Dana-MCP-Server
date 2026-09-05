#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from multiprocessing import current_process
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .config import settings
from .terminal_ui import worker_event, worker_ready
from .reporting import update_report
from .tools import register_tools

# Keep internal MCP lifecycle/tool-registration messages out of Dana's user-facing
# terminal. Worker completion events are emitted through terminal_ui instead.
# The MCP SDK emits request/validation messages at INFO/WARNING. Dana uses
# its own compact worker line instead, so suppress the SDK noise completely.
for _logger_name in (
    "mcp",
    "mcp.server",
    "mcp.server.lowlevel.server",
    "mcp.server.fastmcp",
    "mcp.server.fastmcp.tools.tool_manager",
    "mcp.server.streamable_http_manager",
    "mcp.server.streamable_http",
):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.CRITICAL)
    _logger.propagate = False


_DEFAULT_WORKER_NAMES = [
    "Atlas",
    "Nova",
    "Orion",
    "Vega",
    "Echo",
    "Luna",
    "Pixel",
    "Nexus",
    "Iris",
    "Argo",
    "Cobalt",
    "Milo",
    "Astra",
    "Onyx",
    "Raven",
    "Sol",
    "Kairo",
    "Zephyr",
    "Axiom",
    "Ember",
    "Sage",
    "Bolt",
    "Lyra",
    "Quill",
    "Phoenix",
    "Cosmo",
    "Drift",
    "Halo",
    "Indigo",
    "Juno",
    "Mars",
    "River",
    "Storm",
    "Titan",
    "Willow",
    "Zen",
    "Orbit",
    "Comet",
    "Frost",
    "Dawn",
]


def _worker_names() -> list[str]:
    config = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), ".dana_workers.json"
    )
    try:
        with open(config, encoding="utf-8") as handle:
            names = json.load(handle).get("workers", [])
        if (
            isinstance(names, list)
            and names
            and all(isinstance(n, str) and n.strip() for n in names)
        ):
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
    """Return a deterministic Worker name for this Dana installation.

    The authentication token is unique to the installation and therefore acts
    as the stable seed. Worker #N always receives the same name for that user,
    even after Dana is restarted or the machine is rebooted.
    """
    try:
        from .config import settings

        seed = settings.require_auth_token()
    except (AttributeError, RuntimeError, ValueError):
        seed = os.getenv("DANA_AUTH_TOKEN", "dana")

    names = _worker_names()
    if number <= len(names):
        return names[number - 1]

    ranked = sorted(
        names,
        key=lambda name: hashlib.sha256(f"{seed}:worker:{name}".encode()).hexdigest(),
    )
    return ranked[(number - 1) % len(ranked)]


WORKER_NUMBER = _worker_number()
WORKER_NAME = _worker_name(WORKER_NUMBER)

_allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
if settings.public_host:
    _allowed_hosts.extend([settings.public_host, f"{settings.public_host}:*"])
_allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
if settings.public_host:
    _allowed_origins.append(f"https://{settings.public_host}")
if settings.allowed_origins:
    _allowed_origins.extend(x.strip() for x in settings.allowed_origins.split(",") if x.strip())

mcp = FastMCP(
    "Dana",
    host="127.0.0.1",
    port=8765,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts,
        allowed_origins=_allowed_origins,
    ),
    stateless_http=True,
)
register_tools(mcp)


# FastMCP centralizes every tool invocation through ToolManager.call_tool.
# Wrapping that one point gives us one consistent worker/job log without
# touching the dozens of individual tools.
_original_call_tool = mcp._tool_manager.call_tool


async def _logged_call_tool(
    name: str,
    arguments: dict[str, Any],
    context: Any = None,
    convert_result: bool = False,
) -> Any:
    started = time.perf_counter()
    input_tokens = _estimate_tokens(arguments)
    token_exact = False
    token_source = "tiktoken"
    success = True
    try:
        result = await _original_call_tool(
            name, arguments, context=context, convert_result=convert_result
        )
        usage = _reported_usage(result)
        if usage is not None:
            input_tokens, output_tokens = usage
            token_exact = True
            token_source = "provider_reported"
        else:
            output_tokens = _estimate_tokens(result)
        return result
    except Exception:
        success = False
        output_tokens = 0
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        report_name = name
        if (
            name == "dana_call_tool"
            and isinstance(arguments, dict)
            and arguments.get("name")
        ):
            report_name = str(arguments["name"])
        update_report(report_name, WORKER_NAME, WORKER_NUMBER, input_tokens, output_tokens, duration_ms, success, token_exact, token_source)
        worker_event(
            WORKER_NAME,
            WORKER_NUMBER,
            report_name,
            input_tokens,
            output_tokens,
            duration_ms,
            success,
        )


def _token_text(value: Any) -> str:
    """Return the payload text that a client actually receives, not its Python repr.

    FastMCP wraps tool results in CallToolResult. Serializing that Pydantic model
    with ``default=str`` turns it into a verbose Python representation containing
    field names, ``None`` values and type wrappers. That was inflating output-token
    estimates substantially. Prefer the MCP content blocks and only fall back to
    structured content when there is no textual content.
    """
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
            if parts:
                return "\\n".join(parts)
        if "structuredContent" in value and value.get("structuredContent") is not None:
            try:
                return json.dumps(value["structuredContent"], ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return str(value["structuredContent"])

    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value)


def _estimate_tokens(value: Any) -> int:
    text = _token_text(value)
    if not text:
        return 0
    try:
        import tiktoken  # type: ignore
        model = os.getenv("DANA_TOKENIZER_MODEL", "gpt-4o")
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding(os.getenv("DANA_TOKENIZER_ENCODING", "o200k_base"))
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return max(0, (len(text) + 3) // 4)


def _reported_usage(value: Any) -> tuple[int, int] | None:
    """Extract provider/client usage when a tool result carries it.

    MCP itself does not expose the host LLM's hidden `open call tool` metadata
    to the server, so host-side usage is exact only when the client forwards it.
    """
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
worker_ready(WORKER_NAME, WORKER_NUMBER)
