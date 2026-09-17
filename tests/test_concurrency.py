import asyncio
import sys
import time

from dana.server import mcp


def test_sync_tools_execute_concurrently_across_worker_slots():
    async def run_pair():
        started = time.perf_counter()
        await asyncio.gather(
            mcp._tool_manager.call_tool(
                "run_process", {"command": [sys.executable, "-c", "import time; time.sleep(0.4)"]}, convert_result=False
            ),
            mcp._tool_manager.call_tool(
                "run_process", {"command": [sys.executable, "-c", "import time; time.sleep(0.4)"]}, convert_result=False
            ),
        )
        return time.perf_counter() - started

    elapsed = asyncio.run(run_pair())
    assert elapsed < 0.75


def test_worker_status_exposes_capacity():
    result = asyncio.run(
        mcp._tool_manager.call_tool("dana_worker_status", {}, convert_result=False)
    )
    assert result["workers"] >= 1
    assert result["active"] >= 0
    assert result["idle"] >= 0
    assert len(result["slots"]) == result["workers"]



def test_gateway_batch_uses_real_worker_concurrency():
    async def run_batch():
        started = time.perf_counter()
        result = await mcp._tool_manager.call_tool(
            "dana_batch_call",
            {
                "calls": [
                    {"name": "run_process", "arguments": {"command": [sys.executable, "-c", "import time; time.sleep(0.25)"]}},
                    {"name": "run_process", "arguments": {"command": [sys.executable, "-c", "import time; time.sleep(0.25)"]}},
                ],
                "parallel": True,
            },
            convert_result=False,
        )
        return time.perf_counter() - started, result

    elapsed, result = asyncio.run(run_batch())
    assert elapsed < 0.55
    assert result["count"] == 2
    assert all(item["ok"] for item in result["results"])
