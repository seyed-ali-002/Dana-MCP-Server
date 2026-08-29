def test_formatting_tools_import():
    from dana.tools.formatting import register_formatting_tools
    assert callable(register_formatting_tools)

def test_formatting_tools_registered():
    import asyncio
    from dana.server import mcp
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"format_python", "lint_python", "sort_python_imports", "type_check_python", "check_code_quality", "format_code"} <= names
