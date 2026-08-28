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
