from __future__ import annotations

from collections import defaultdict
from typing import Any

# Canonical capability groups used by discovery and diagnostics. Internal tools may
# remain for compatibility, but discovery presents one consistent vocabulary.
CATEGORY_KEYWORDS = {
    "system": ("system_", "process_", "environment", "network_", "port_", "toolchain"),
    "filesystem": ("file", "directory", "path", "workspace", "snapshot", "search_code"),
    "engineering": ("test", "lint", "format", "type_check", "build", "coverage", "benchmark", "debug"),
    "codebase": ("codebase", "symbol", "project_", "architecture", "dependency", "duplicate", "entry_point"),
    "documents": ("document", "pdf", "docx", "readme", "changelog", "report"),
    "web": ("http", "api_", "web_", "browser", "library_docs"),
    "memory": ("memory", "context"),
    "security": ("security", "secret", "allowed_path", "access_policy"),
    "design": ("ui_", "sashimi", "persian", "design_"),
    "runtime": ("dana_", "task_", "schedule", "token_"),
    "godot": ("godot_", "godot"),
    "desktop": ("desktop_", "ydotool", "screenshot", "wmctrl"),
}

# Search aliases normalize the inconsistent historical naming without breaking
# existing clients that call internal tool names directly.
ALIASES = {
    "ui": ("dana_create_ui_design", "dana_create_sashimi_ui", "dana_export_ui_html", "dana_export_sashimi_html"),
    "format": ("format_code", "format_project", "format_python", "sort_python_imports"),
    "pdf": ("create_pdf", "extract_pdf_text", "extract_pdfs_text"),
    "project analysis": ("analyze_project", "dana_map_repository", "architecture_summary"),
    "code quality": ("check_code_quality", "static_analysis", "lint_or_format"),
    "godot": ("godot_health_check", "godot_project_info", "godot_list_scenes", "godot_call"),
}


def category_for(name: str) -> str:
    value = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in value for keyword in keywords):
            return category
    return "general"


def canonical_name(name: str) -> str:
    # Preserve exact executable names. Canonicalization is a presentation layer.
    return name


def _annotation_dict(tool: Any) -> dict[str, Any] | None:
    raw = getattr(tool, "annotations", None)
    if raw is None:
        return None
    if hasattr(raw, "model_dump"):
        try:
            data = raw.model_dump(exclude_none=True)
            return data or None
        except Exception:
            pass
    out: dict[str, Any] = {}
    for key in ("title", "readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
        val = getattr(raw, key, None)
        if val is not None:
            out[key] = val
    return out or None


def enrich(tool: Any) -> dict[str, Any]:
    item = {
        "name": tool.name,
        "canonical_name": canonical_name(tool.name),
        "category": category_for(tool.name),
        "description": (tool.description or "").strip() or f"Dana {category_for(tool.name)} capability: {tool.name}.",
        "input_schema": tool.parameters,
    }
    ann = _annotation_dict(tool)
    if ann:
        item["annotations"] = ann
    return item


def catalog(tools: list[Any]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for tool in tools:
        groups[category_for(tool.name)].append(tool.name)
    return {key: sorted(value) for key, value in sorted(groups.items())}
