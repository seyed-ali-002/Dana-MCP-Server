# mcp-tool-quality

Use when adding or rewriting Dana MCP tools.

## Rules
- Docstring must match real behavior.
- Annotate with READ_ONLY / DESTRUCTIVE / MUTATING / OPEN_WORLD (`dana.tools.mcp_quality`).
- Failures raise (FR-016); never return success with an error string.
- Paths through `require_path`; subprocess via `clean_subprocess_env()`.
- List tools: limit/offset or paginate(); default limits 20–50.
- Prefer actionable_error with next_steps and related_tools.

See project_description_md/18-mcp-tool-quality.md.
