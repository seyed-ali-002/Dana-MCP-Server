def test_formatting_tools_import():
    from dana.tools.formatting import register_formatting_tools

    assert callable(register_formatting_tools)


def test_formatting_tools_registered():
    import asyncio
    from dana.server import mcp

    names = set(mcp._tool_manager._tools)
    assert {
        "format_python",
        "lint_python",
        "sort_python_imports",
        "type_check_python",
        "check_code_quality",
        "format_code",
        "format_python_check",
        "fix_python_code",
        "check_prettier",
        "lint_javascript",
        "format_project",
        "toolchain_status",
    } <= names
