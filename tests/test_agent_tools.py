from dana.server import mcp


def test_agent_tools_registered():
    names = {tool.name for tool in mcp._tool_manager._tools.values()}
    required = {
        "read_file", "write_file", "edit_file", "delete_path", "search_code",
        "run_command", "run_process", "process_list", "process_stop", "read_log",
        "debug_trace", "git", "run_tests", "lint_or_format", "package_manager",
        "build_project", "environment", "http_request", "sqlite_query", "docker",
        "network_check", "system_details", "schedule_command", "cancel_scheduled_task",
        "browser_automation",
    }
    assert required <= names



def test_edit_file_recovers_trailing_whitespace_drift(tmp_path):
    import asyncio

    target = tmp_path / "sample.py"
    target.write_text("value = 1  \nprint(value)\n", encoding="utf-8")
    result = asyncio.run(
        mcp._tool_manager.call_tool(
            "edit_file",
            {"path": str(target), "old": "value = 1\n", "new": "value = 2\n"},
            convert_result=False,
        )
    )
    assert result["matches"] == 1
    assert result["match_mode"] == "whitespace_normalized"
    assert "value = 2" in target.read_text(encoding="utf-8")
