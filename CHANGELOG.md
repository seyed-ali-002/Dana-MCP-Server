# Changelog

All notable changes to **Dana MCP Server** are documented here.
Format: keep user-visible and API-relevant entries. Internal refactors optional.

## [Unreleased]

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
