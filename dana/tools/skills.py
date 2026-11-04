from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from dana import skills_registry as skills


def register_skills_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_skills() -> dict[str, Any]:
        """List available Dana skills (bundled, user, project, and extra paths)."""
        return skills.list_skills()

    @mcp.tool()
    def get_skill(skill_id: str) -> dict[str, Any]:
        """Load one skill by id (markdown body + metadata)."""
        return skills.get_skill(skill_id)

    @mcp.tool()
    def set_skill_enabled(skill_id: str, enabled: bool = True) -> dict[str, Any]:
        """Enable or disable a skill for agent context."""
        return skills.set_skill_enabled(skill_id, bool(enabled))

    @mcp.tool()
    def install_skill(name: str, content: str) -> dict[str, Any]:
        """Install a skill from pasted markdown/text into ~/.config/dana/skills."""
        return skills.install_skill_text(name, content)

    @mcp.tool()
    def import_skill_file(path: str) -> dict[str, Any]:
        """Copy a skill file from disk into the user skills directory."""
        return skills.import_skill_file(path)

    @mcp.tool()
    def add_skill_path(path: str) -> dict[str, Any]:
        """Register an extra directory or file path for skill discovery."""
        return skills.add_skill_path(path)

    @mcp.tool()
    def import_skill_pack(pack: str) -> dict[str, Any]:
        """Import markdown skills from a known upstream pack (agency-agents, superpowers, …)."""
        return skills.import_skill_pack(pack)

    @mcp.tool()
    def remove_skill(skill_id: str) -> dict[str, Any]:
        """Remove a user-installed skill (bundled packs are protected)."""
        return skills.remove_skill(skill_id)

    @mcp.tool()
    def skill_context(max_chars: int = 12000) -> dict[str, Any]:
        """Return concatenated enabled skill instructions for the agent context."""
        text = skills.active_skill_context(max_chars=max(1000, min(max_chars, 50000)))
        return {"ok": True, "chars": len(text), "context": text}
