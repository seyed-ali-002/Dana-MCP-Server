from __future__ import annotations

import hashlib
import logging
import json
import os
import time
from multiprocessing import current_process
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .terminal_ui import worker_event, worker_ready
from .tools import register_tools


# Keep internal MCP lifecycle/tool-registration messages out of Dana's user-facing
# terminal. Worker completion events are emitted through terminal_ui instead.
for _logger_name in (
    "mcp.server.fastmcp.tools.tool_manager",
    "mcp.server.streamable_http_manager",
    "mcp.server.streamable_http",
):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.ERROR)
    _logger.propagate = False


_DEFAULT_WORKER_NAMES = [
    "Atlas", "Nova", "Orion", "Vega", "Echo", "Luna", "Pixel", "Nexus",
    "Iris", "Argo", "Cobalt", "Milo", "Astra", "Onyx", "Raven", "Sol",
    "Kairo", "Zephyr", "Axiom", "Ember", "Sage", "Bolt", "Lyra", "Quill",
    "Phoenix", "Cosmo", "Drift", "Halo", "Indigo", "Juno", "Mars", "River",
    "Storm", "Titan", "Willow", "Zen", "Orbit", "Comet", "Frost", "Dawn",
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
    """Return a deterministic Worker name for this Dana installation.

    The authentication token is unique to the installation and therefore acts
    as the stable seed. Worker #N always receives the same name for that user,
    even after Dana is restarted or the machine is rebooted.
    """
    try:
        from .config import settings
        seed = settings.require_auth_token()
    except Exception:
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

mcp = FastMCP(
    "Dana",
    host="127.0.0.1",
    port=8765,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
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
    success = True
    try:
        result = await _original_call_tool(name, arguments, context=context, convert_result=convert_result)
        output_tokens = _estimate_tokens(result)
        return result
    except Exception:
        success = False
        output_tokens = 0
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        worker_event(
            WORKER_NAME,
            WORKER_NUMBER,
            name,
            input_tokens,
            output_tokens,
            duration_ms,
            success,
        )


def _estimate_tokens(value: Any) -> int:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    except Exception:
        text = str(value)
    return max(0, (len(text) + 3) // 4)


mcp._tool_manager.call_tool = _logged_call_tool
worker_ready(WORKER_NAME, WORKER_NUMBER)
