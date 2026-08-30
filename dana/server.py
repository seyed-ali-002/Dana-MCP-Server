from __future__ import annotations

import hashlib
import json
import os
import time
from multiprocessing import current_process
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .terminal_ui import worker_event, worker_ready
from .tools import register_tools


_WORKER_NAMES = [
    "Atlas", "Nova", "Orion", "Vega", "Echo", "Luna", "Pixel", "Nexus",
    "Iris", "Argo", "Cobalt", "Milo", "Astra", "Onyx", "Raven", "Sol",
    "Kairo", "Zephyr", "Axiom", "Ember", "Sage", "Bolt", "Lyra", "Quill",
]


def _worker_number() -> int:
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

    ranked = sorted(
        _WORKER_NAMES,
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
