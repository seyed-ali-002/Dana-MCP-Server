from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _project(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load(path: Path) -> dict[str, Any]:
    return (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {
            "version": 1,
            "theme": "material-3-expressive",
            "screens": [],
            "connections": [],
        }
    )


def _save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_design_engine_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_create_ui_design(
        path: str, name: str, description: str = ""
    ) -> dict[str, Any]:
        """Create a persistent UI canvas model inspired by M3E Canvas."""
        root = _project(path)
        target = root / "dana-design.json"
        data = {
            "id": uuid.uuid4().hex,
            "name": name,
            "description": description,
            "version": 1,
            "theme": "material-3-expressive",
            "screens": [],
            "connections": [],
        }
        _save(target, data)
        return {"design": str(target), "data": data}

    @mcp.tool()
    def dana_add_ui_screen(
        path: str, name: str, route: str | None = None, purpose: str = ""
    ) -> dict[str, Any]:
        """Add a screen to Dana's persistent UI design model."""
        target = _project(path) / "dana-design.json"
        data = _load(target)
        screen = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "route": route or "/" + name.lower().replace(" ", "-"),
            "purpose": purpose,
            "components": [],
        }
        data["screens"].append(screen)
        _save(target, data)
        return {"screen": screen, "design": str(target)}

    @mcp.tool()
    def dana_add_ui_component(
        path: str, screen_id: str, component: str, props: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Add a component definition to a design screen."""
        target = _project(path) / "dana-design.json"
        data = _load(target)
        for screen in data["screens"]:
            if screen["id"] == screen_id:
                item = {
                    "id": uuid.uuid4().hex[:12],
                    "type": component,
                    "props": props or {},
                }
                screen["components"].append(item)
                _save(target, data)
                return item
        raise ValueError(f"Screen not found: {screen_id}")

    @mcp.tool()
    def dana_connect_ui_screens(
        path: str, from_screen: str, to_screen: str, action: str = "navigate"
    ) -> dict[str, Any]:
        """Connect two screens to describe navigation flow."""
        target = _project(path) / "dana-design.json"
        data = _load(target)
        edge = {"from": from_screen, "to": to_screen, "action": action}
        data["connections"].append(edge)
        _save(target, data)
        return edge

    @mcp.tool()
    def dana_generate_ui_prompt(path: str, target: str = "react") -> dict[str, Any]:
        """Convert the visual design model into an implementation-ready prompt."""
        design = _load(_project(path) / "dana-design.json")
        screens = "; ".join(
            f"{s['name']} ({s['route']}): {s['purpose']}" for s in design["screens"]
        )
        prompt = f"Implement {design.get('name', 'this application')} for {target}. Use {design.get('theme')}. Screens: {screens}. Follow the JSON design model for components and navigation."
        return {"target": target, "prompt": prompt, "design": design}

    @mcp.tool()
    def dana_export_ui_html(path: str, output: str | None = None) -> dict[str, Any]:
        """Export a lightweight HTML preview from the design model."""
        root = _project(path)
        design = _load(root / "dana-design.json")
        out = (
            Path(output).expanduser().resolve()
            if output
            else root / "dana-design-preview.html"
        )
        sections = []
        for screen in design["screens"]:
            items = "".join(
                "<li>"
                + c["type"]
                + ": "
                + json.dumps(c["props"], ensure_ascii=False)
                + "</li>"
                for c in screen["components"]
            )
            sections.append(
                "<section><h2>"
                + screen["name"]
                + "</h2><p>"
                + screen["purpose"]
                + "</p><ul>"
                + items
                + "</ul></section>"
            )
        html = (
            "<!doctype html><html><meta charset='utf-8'><title>"
            + design.get("name", "Dana Design")
            + "</title><body><h1>"
            + design.get("name", "Dana Design")
            + "</h1>"
            + "".join(sections)
            + "</body></html>"
        )
        out.write_text(html, encoding="utf-8")
        return {"output": str(out), "screens": len(design["screens"])}
