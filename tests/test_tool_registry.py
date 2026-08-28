import asyncio
from dana.server import mcp

REQUIRED = {
    "system_info", "list_directory", "read_file", "write_file", "edit_file", "delete_path",
    "search_code", "run_command", "run_process", "process_list", "process_stop",
    "git", "run_tests", "lint_or_format", "package_manager", "build_project",
    "http_request", "sqlite_query", "docker", "network_check", "browser_automation",
    "web_fetch", "api_request", "discover_tests", "static_analysis", "coverage",
    "benchmark", "debug_command", "python_diagnostics", "generate_readme",
    "generate_changelog", "architecture_summary", "generate_project_diagram", "generate_report",
}

def test_required_tools_are_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert REQUIRED <= names
