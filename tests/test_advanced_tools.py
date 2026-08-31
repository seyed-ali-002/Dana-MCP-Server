import asyncio
from dana.server import mcp


def test_advanced_tools_registered():
    names = set(mcp._tool_manager._tools)
    required = {
        "analyze_project",
        "find_entry_points",
        "project_health_check",
        "find_duplicate_code",
        "browser_open",
        "database_schema",
        "database_health_check",
        "docker_status",
        "container_logs",
        "docker_build",
        "secret_scan",
        "dependency_security_scan",
        "dependency_outdated",
        "analyze_stacktrace",
        "tail_logs",
        "search_logs",
        "system_metrics",
        "port_check",
        "find_symbol",
        "find_references",
        "code_complexity",
        "create_task_plan",
        "task_status",
        "change_summary",
        "workspace_snapshot",
        "rollback_changes",
    }
    assert required <= names
