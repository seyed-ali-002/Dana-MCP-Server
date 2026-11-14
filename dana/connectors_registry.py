"""User-managed MCP connectors registry for SuperMCP multi-server config.

Stores extra mcpServers entries (stdio / HTTP / SSE) under the Dana data dir so
write_config() can merge them with the built-in Dana upstream. Format matches the
common Claude Desktop / Cursor mcpServers JSON shape, e.g.:

{
  "mcpServers": {
    "godot": {
      "command": "npx",
      "args": ["@coding-solo/godot-mcp"],
      "env": {"GODOT_PATH": "/path/to/Godot"}
    }
  }
}
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    path = base / "dana" / "connectors"
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_path() -> Path:
    return _data_dir() / "user_connectors.json"


def _default_payload() -> dict[str, Any]:
    return {"mcpServers": {}, "version": 1}


def load_user_connectors() -> dict[str, dict[str, Any]]:
    """Return the mcpServers map (name -> config). Never raises."""
    path = registry_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    servers = raw.get("mcpServers")
    if not isinstance(servers, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, cfg in servers.items():
        if isinstance(name, str) and isinstance(cfg, dict) and _NAME_RE.match(name):
            out[name] = dict(cfg)
    return out


def save_user_connectors(servers: dict[str, dict[str, Any]]) -> Path:
    """Persist the full mcpServers map. Validates names; strips reserved 'Dana'."""
    cleaned: dict[str, dict[str, Any]] = {}
    for name, cfg in (servers or {}).items():
        if not isinstance(name, str) or not _NAME_RE.match(name):
            continue
        if name.lower() == "dana":
            continue  # reserved for the built-in upstream
        if not isinstance(cfg, dict):
            continue
        cleaned[name] = _normalize_server_cfg(cfg)
    path = registry_path()
    payload = {"mcpServers": cleaned, "version": 1}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _normalize_server_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Keep only well-known keys used by SuperMCP / mcp-superassistant-proxy."""
    out: dict[str, Any] = {}
    # stdio style
    if isinstance(cfg.get("command"), str) and cfg["command"].strip():
        out["command"] = cfg["command"].strip()
    if isinstance(cfg.get("args"), list):
        out["args"] = [str(a) for a in cfg["args"]]
    if isinstance(cfg.get("env"), dict):
        out["env"] = {str(k): str(v) for k, v in cfg["env"].items() if k is not None}
    if isinstance(cfg.get("cwd"), str) and cfg["cwd"].strip():
        out["cwd"] = cfg["cwd"].strip()
    # HTTP / SSE / Streamable HTTP style
    if isinstance(cfg.get("url"), str) and cfg["url"].strip():
        out["url"] = cfg["url"].strip()
    if isinstance(cfg.get("headers"), dict):
        out["headers"] = {str(k): str(v) for k, v in cfg["headers"].items() if k is not None}
    if isinstance(cfg.get("transport"), str) and cfg["transport"].strip():
        out["transport"] = cfg["transport"].strip()
    if isinstance(cfg.get("toolManifest"), str) and cfg["toolManifest"].strip():
        out["toolManifest"] = cfg["toolManifest"].strip()
    # optional metadata for UI
    if isinstance(cfg.get("description"), str):
        out["description"] = cfg["description"][:500]
    if isinstance(cfg.get("enabled"), bool):
        out["enabled"] = cfg["enabled"]
    else:
        out.setdefault("enabled", True)
    return out


def list_connectors() -> list[dict[str, Any]]:
    """Flat list for the UI: name + config + kind."""
    servers = load_user_connectors()
    rows: list[dict[str, Any]] = []
    for name, cfg in sorted(servers.items()):
        kind = "stdio" if cfg.get("command") else ("http" if cfg.get("url") else "unknown")
        rows.append(
            {
                "name": name,
                "kind": kind,
                "enabled": bool(cfg.get("enabled", True)),
                "command": cfg.get("command") or "",
                "args": cfg.get("args") or [],
                "env": cfg.get("env") or {},
                "cwd": cfg.get("cwd") or "",
                "url": cfg.get("url") or "",
                "headers": cfg.get("headers") or {},
                "transport": cfg.get("transport") or "",
                "description": cfg.get("description") or "",
                "config": cfg,
            }
        )
    return rows


def upsert_connector(name: str, config: dict[str, Any]) -> dict[str, Any]:
    """Add or replace one connector. Returns {ok, message, name, config}."""
    name = (name or "").strip()
    if not _NAME_RE.match(name):
        return {"ok": False, "message": "Invalid connector name. Use letters, digits, . _ - (max 64)."}
    if name.lower() == "dana":
        return {"ok": False, "message": "Name 'Dana' is reserved for the built-in upstream server."}
    if not isinstance(config, dict):
        return {"ok": False, "message": "Config must be an object."}
    normalized = _normalize_server_cfg(config)
    if not normalized.get("command") and not normalized.get("url"):
        return {"ok": False, "message": "Provide either command (stdio) or url (HTTP/SSE)."}
    servers = load_user_connectors()
    servers[name] = normalized
    save_user_connectors(servers)
    return {"ok": True, "message": f"Connector '{name}' saved.", "name": name, "config": normalized}


def remove_connector(name: str) -> dict[str, Any]:
    name = (name or "").strip()
    servers = load_user_connectors()
    if name not in servers:
        return {"ok": False, "message": f"Connector '{name}' not found."}
    del servers[name]
    save_user_connectors(servers)
    return {"ok": True, "message": f"Connector '{name}' removed."}


def import_mcp_servers(payload: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    """Import from Claude/Cursor-style JSON: {\"mcpServers\": {...}} or a bare servers map."""
    if payload is None:
        return {"ok": False, "message": "Empty payload."}
    servers_in: dict[str, Any] = {}
    if isinstance(payload, dict):
        if isinstance(payload.get("mcpServers"), dict):
            servers_in = payload["mcpServers"]
        else:
            # bare map of name -> config
            servers_in = {k: v for k, v in payload.items() if isinstance(v, dict)}
    else:
        return {"ok": False, "message": "Payload must be a JSON object."}
    existing = load_user_connectors()
    added: list[str] = []
    skipped: list[str] = []
    for name, cfg in servers_in.items():
        if not isinstance(name, str) or not _NAME_RE.match(name):
            skipped.append(str(name))
            continue
        if name.lower() == "dana":
            skipped.append(name)
            continue
        if not isinstance(cfg, dict):
            skipped.append(name)
            continue
        normalized = _normalize_server_cfg(cfg)
        if not normalized.get("command") and not normalized.get("url"):
            skipped.append(name)
            continue
        existing[name] = normalized
        added.append(name)
    save_user_connectors(existing)
    return {
        "ok": True,
        "message": f"Imported {len(added)} connector(s).",
        "added": added,
        "skipped": skipped,
        "total": len(existing),
    }


def export_mcp_servers() -> dict[str, Any]:
    """Shape suitable for pasting into other MCP clients."""
    return {"mcpServers": load_user_connectors()}
