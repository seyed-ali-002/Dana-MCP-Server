from __future__ import annotations

import html
import json
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _root(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _class(prefix: bool, name: str) -> str:
    return f"sui-{name}" if prefix else name


def _render_component(component: dict[str, Any], prefix: bool) -> str:
    ctype = component.get("type", "card")
    props = component.get("props", {})
    title = html.escape(str(props.get("title", props.get("label", ""))))
    text = html.escape(str(props.get("text", props.get("description", ""))))
    button = html.escape(str(props.get("button", props.get("action", ""))))
    if ctype in {"hero", "header"}:
        return f"<section class='{_class(prefix, "hero")}'><h1>{title}</h1><p>{text}</p>{f"<button class='{_class(prefix, "button")}'>{button}</button>" if button else ""}</section>"
    if ctype in {"button", "action"}:
        return f"<button class='{_class(prefix, "button")}'>{title or text}</button>"
    if ctype in {"input", "field"}:
        return f"<label class='{_class(prefix, "field")}'>{title}<input placeholder='{text}'></label>"
    if ctype in {"list", "menu"}:
        items = props.get("items", [])
        if not isinstance(items, list):
            items = [items]
        return f"<ul class='{_class(prefix, "list")}'>{''.join(f"<li>{html.escape(str(item))}</li>" for item in items)}</ul>"
    return f"<article class='{_class(prefix, "card")}'><h2>{title}</h2><p>{text}</p>{f"<button class='{_class(prefix, "button")}'>{button}</button>" if button else ""}</article>"


def _theme_css(prefix: bool) -> str:
    p = "sui-" if prefix else ""
    return f"""
:root {{ color-scheme: dark; --bg:#0b1020; --surface:#121a2b; --surface-2:#18233a; --text:#eef4ff; --muted:#9ba9c5; --accent:#64b5ff; --line:rgba(255,255,255,.11); }}
* {{ box-sizing:border-box; }} body {{ margin:0; min-height:100vh; font-family:Inter,Arial,sans-serif; background:radial-gradient(circle at top left,#18345f 0,transparent 32%),var(--bg); color:var(--text); }}
.{p}app {{ max-width:1180px; margin:auto; padding:28px; }} .{p}hero,.{p}card {{ background:linear-gradient(145deg,rgba(255,255,255,.08),rgba(255,255,255,.03)); border:1px solid var(--line); border-radius:24px; padding:28px; box-shadow:0 24px 70px rgba(0,0,0,.25); }}
.{p}hero {{ margin-bottom:20px; }} .{p}grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; }} .{p}card h2,.{p}hero h1 {{ margin-top:0; }} .{p}card p,.{p}hero p {{ color:var(--muted); line-height:1.7; }}
.{p}button {{ border:0; border-radius:14px; padding:12px 18px; background:var(--accent); color:#07111f; font-weight:700; cursor:pointer; }} .{p}field {{ display:grid; gap:8px; color:var(--muted); }} input {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:12px; background:var(--surface-2); color:var(--text); }}
.{p}list {{ list-style:none; padding:0; margin:0; display:grid; gap:8px; }} .{p}list li {{ padding:12px 14px; border:1px solid var(--line); border-radius:12px; background:rgba(255,255,255,.03); }}
"""


def register_sashimi_ui_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_create_sashimi_ui(path: str, name: str, description: str = "", prefixed_classes: bool = True) -> dict[str, Any]:
        """Create a lightweight, dependency-free Sashimi-inspired UI project model."""
        root = _root(path)
        data = {
            "id": uuid.uuid4().hex,
            "name": name,
            "description": description,
            "style": "sashimi-inspired",
            "prefixed_classes": prefixed_classes,
            "screens": [],
        }
        target = root / "dana-sashimi-ui.json"
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ui": str(target), "data": data}

    @mcp.tool()
    def dana_add_sashimi_screen(path: str, name: str, title: str = "", description: str = "") -> dict[str, Any]:
        """Add a screen to a Sashimi-inspired Dana UI model."""
        target = _root(path) / "dana-sashimi-ui.json"
        data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"name": "Dana UI", "screens": [], "prefixed_classes": True}
        screen = {"id": uuid.uuid4().hex[:12], "name": name, "title": title or name, "description": description, "components": []}
        data["screens"].append(screen)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"screen": screen, "ui": str(target)}

    @mcp.tool()
    def dana_add_sashimi_component(path: str, screen_id: str, component: str, props: dict[str, Any] | None = None) -> dict[str, Any]:
        """Add a component such as hero, card, button, input or list."""
        target = _root(path) / "dana-sashimi-ui.json"
        data = json.loads(target.read_text(encoding="utf-8"))
        for screen in data.get("screens", []):
            if screen["id"] == screen_id:
                item = {"id": uuid.uuid4().hex[:12], "type": component, "props": props or {}}
                screen["components"].append(item)
                target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return item
        raise ValueError(f"Screen not found: {screen_id}")

    @mcp.tool()
    def dana_export_sashimi_html(path: str, output: str | None = None) -> dict[str, Any]:
        """Export a polished responsive HTML preview using Sashimi-inspired component conventions."""
        root = _root(path)
        source = root / "dana-sashimi-ui.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        prefix = bool(data.get("prefixed_classes", True))
        app = _class(prefix, "app")
        grid = _class(prefix, "grid")
        sections: list[str] = []
        for screen in data.get("screens", []):
            components = screen.get("components", [])
            body = "".join(_render_component(c, prefix) for c in components)
            sections.append(f"<section class='{app}'><header><h1>{html.escape(screen.get("title", screen["name"]))}</h1><p>{html.escape(screen.get("description", ""))}</p></header><div class='{grid}'>{body}</div></section>")
        target = Path(output).expanduser().resolve() if output else root / "dana-sashimi-preview.html"
        page = f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(data.get("name", "Dana UI"))}</title><style>{_theme_css(prefix)}</style></head><body>{''.join(sections)}</body></html>"
        target.write_text(page, encoding="utf-8")
        return {"output": str(target), "screens": len(data.get("screens", [])), "style": "sashimi-inspired"}
