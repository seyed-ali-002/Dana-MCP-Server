from __future__ import annotations

import hashlib
import logging
import json
import os
import time
from pathlib import Path
from multiprocessing import current_process
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .terminal_ui import worker_event, worker_ready

REPORT_JSON = Path(__file__).resolve().parents[1] / ".dana" / "report.json"
REPORT_HTML = Path(__file__).resolve().parents[1] / "report.html"


def update_report(tool, input_tokens, output_tokens, duration_ms, success):
    try:
        REPORT_JSON.parent.mkdir(exist_ok=True)
        try:
            data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        except Exception:
            data = {
                "start": time.time(),
                "last": None,
                "input": 0,
                "output": 0,
                "duration": 0,
                "operations": 0,
                "events": [],
            }
        now = time.time()
        data["last"] = now
        data["input"] += input_tokens
        data["output"] += output_tokens
        data["duration"] += duration_ms
        data["operations"] += 1
        data["events"].append(
            {
                "time": now,
                "worker": WORKER_NAME,
                "number": WORKER_NUMBER,
                "tool": tool,
                "input": input_tokens,
                "output": output_tokens,
                "duration": duration_ms,
                "success": success,
            }
        )
        data["events"] = data["events"][-1000:]
        REPORT_JSON.write_text(json.dumps(data), encoding="utf-8")
        rows = "".join(
            "<tr><td>%s</td><td>%s #%s</td><td>%s</td><td>%s</td><td>%s</td><td>%.0fms</td><td>%s</td></tr>"
            % (
                time.ctime(e["time"]),
                e["worker"],
                e["number"],
                e["tool"],
                e["input"],
                e["output"],
                e["duration"],
                "DONE" if e["success"] else "FAIL",
            )
            for e in reversed(data["events"])
        )
        REPORT_HTML.write_text(
            "<meta http-equiv='refresh' content='5'><style>body{font:15px system-ui;background:#08111f;color:#eee;padding:30px;max-width:1200px;margin:auto}.card{display:inline-block;background:#101d30;padding:18px;margin:5px;border-radius:12px}table{width:100%;margin-top:20px}td,th{padding:8px;border-bottom:1px solid #345;text-align:left}</style><h1>DANA Usage Report</h1><p>Live local report; updated after every tool use.</p><div class='card'>TOTAL TOKENS<br><b>%s</b></div><div class='card'>INPUT<br><b>%s</b></div><div class='card'>OUTPUT<br><b>%s</b></div><div class='card'>USAGE TIME<br><b>%.2fs</b></div><div class='card'>OPERATIONS<br><b>%s</b></div><p>Last use: %s</p><table><tr><th>Time</th><th>Worker</th><th>Tool</th><th>Input</th><th>Output</th><th>Duration</th><th>Status</th></tr>%s</table>"
            % (
                data["input"] + data["output"],
                data["input"],
                data["output"],
                data["duration"] / 1000,
                data["operations"],
                time.ctime(data["last"]),
                rows,
            ),
            encoding="utf-8",
        )
    except Exception:
        logging.getLogger("dana").debug("usage report update failed", exc_info=True)


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
        result = await _original_call_tool(
            name, arguments, context=context, convert_result=convert_result
        )
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
        update_report(report_name, input_tokens, output_tokens, duration_ms, success)
        worker_event(
            WORKER_NAME,
            WORKER_NUMBER,
            report_name,
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
