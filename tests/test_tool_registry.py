import asyncio

from dana.server import mcp

REQUIRED = {
    "system_info",
    "list_directory",
    "read_file",
    "write_file",
    "edit_file",
    "delete_path",
    "search_code",
    "run_command",
    "run_process",
    "process_list",
    "process_stop",
    "git",
    "run_tests",
    "lint_or_format",
    "package_manager",
    "build_project",
    "http_request",
    "sqlite_query",
    "docker",
    "network_check",
    "browser_automation",
    "web_fetch",
    "api_request",
    "discover_tests",
    "static_analysis",
    "coverage",
    "benchmark",
    "debug_command",
    "python_diagnostics",
    "generate_readme",
    "generate_changelog",
    "architecture_summary",
    "generate_project_diagram",
    "generate_report",
}

VISIBLE = {
    "dana_search_tools",
    "dana_call_tool",
    "dana_batch_call",
    "dana_capabilities",
    "dana_optimization_stats",
    "dana_context_build",
    "dana_context_compact",
    "dana_result_page",
    "dana_result_optimize",
    "dana_session_start",
    "dana_session_compact",
    "dana_session_get",
    "dana_prompt_cache_key",
}


def test_required_tools_are_registered_in_internal_registry():
    names = set(mcp._tool_manager._tools)
    assert REQUIRED <= names


def test_progressive_surface_is_small():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == VISIBLE
    assert len(names) <= 16


def test_capability_search_and_generic_execution():
    search = asyncio.run(
        mcp._tool_manager.call_tool(
            "dana_search_tools",
            {"query": "system information"},
            context=None,
            convert_result=False,
        )
    )
    assert any(item["name"] == "system_info" for item in search["matches"])

    result = asyncio.run(
        mcp._tool_manager.call_tool(
            "dana_call_tool",
            {"name": "system_info", "arguments": {}},
            context=None,
            convert_result=False,
        )
    )
    assert "os" in result


def test_batch_execution():
    result = asyncio.run(
        mcp._tool_manager.call_tool(
            "dana_batch_call",
            {
                "calls": [
                    {"name": "system_info", "arguments": {}},
                    {"name": "system_metrics", "arguments": {}},
                ]
            },
            context=None,
            convert_result=False,
        )
    )
    assert result["parallel"] is True
    assert result["count"] == 2
    assert all(item["ok"] for item in result["results"])
