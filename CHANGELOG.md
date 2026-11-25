## [Unreleased]

### Added
- Desktop agent layer: setup_input, observe, open/focus/wait/verify, click_element, type_into, accessibility probe
- Wayland uinput/ydotool install helper script under ~/.config/dana/desktop/

## [Unreleased]

### Improved
- MCP tool quality helpers (`mcp_quality`), restored `mcp_result_format`, annotations on agent_planning, list_directory limit/offset, search default limit 50

# Changelog

All notable changes to **Dana MCP Server** are documented here.
Format: keep user-visible and API-relevant entries. Internal refactors optional.

## [Unreleased]

## [2.0.15] — 2026-11-22

### Changed
- Synchronized version metadata across `pyproject.toml`, `ui/package.json`,
  `ui/src-tauri/tauri.conf.json`, and `dana/__init__.py`.
- `dana_capabilities` now reflects **actual** progressive discovery behavior:
  `tools/list` is filtered to the visible set when `DANA_PROGRESSIVE_TOOLS=1`
  (`dana/server.py::_apply_progressive_tool_visibility`). The 90% token-savings
  figure is now real client behavior, not only a metric.

### Fixed
- `requirements.txt` no longer forces optional extras (`playwright`,
  `pyautogui`). Install them via
  `pip install "dana-mcp-server[desktop|browser|full]"` (NFR-006).
- `.env.example` now documents `DANA_CONTEXT_MODE` and
  `DANA_STRIP_OUTPUT_SCHEMA`, and clarifies `DANA_PROGRESSIVE_TOOLS`.
- SRS/Roadmap/CHANGELOG aligned with product version (previously SRS pinned
  2.0.7 while metadata was 2.0.14).

### Documentation
- Mandatory documentation policy (`17-documentation-policy.md`)
- Connectors / SuperMCP / Godot proxy guide (`16-connectors-supermcp-godot.md`)
- CONTRIBUTING.md and root CHANGELOG

## [2.0.7] — 2026-11-22

### Fixed
- **UI (#1):** main content no longer trapped in a fixed-width column; shell fills the grid, scroll works, Tauri min window 720×520 (`7006122`)
- Reporting active-time uses interval union (FR-016)
- `clean_subprocess_env` on Popen/sudo paths (NFR-002)
- Personal `/mnt/...` paths removed from product code
- Agent planning path checks (`require_path`) and task plan helpers (FR-060)

### Added
- Connectors registry + SuperMCP merge + Control Center Connectors tab
- Godot proxy tools registered in Dana native FastMCP registry

### Tests
- 133 pytest cases green on baseline

## [2.0.0] — 2026-11

- Control Center visual baseline, connection modes, SuperMCP integration surface
- See `project_description_md/15-post-2.0-fix-notes.md` for early 2.0.x patches

## Earlier

See git tags `v1.*` and `project_description_md/06-versioning-release.md`.
