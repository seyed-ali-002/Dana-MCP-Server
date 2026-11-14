"""User MCP connectors registry for SuperMCP (stdio / HTTP)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif os.uname().sysname.lower() == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    path = base / "dana" / "supermcp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def connectors_file() -> Path:
    return data_dir() / "connectors.json"


def load_user_connectors() -> dict[str, Any]:
    path = connectors_file()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
        servers = data["mcpServers"]
    elif isinstance(data, dict):
        servers = data
    else:
        return {}
    out: dict[str, Any] = {}
    for name, spec in servers.items():
        key = str(name or "").strip()
        if not key or key.lower() == "dana":
            continue
        if isinstance(spec, dict):
            out[key] = dict(spec)
    return out


def save_user_connectors(servers: dict[str, Any]) -> Path:
    path = connectors_file()
    clean = {
        k: v
        for k, v in servers.items()
        if str(k).strip() and str(k).lower() != "dana" and isinstance(v, dict)
    }
    path.write_text(
        json.dumps({"mcpServers": clean}, indent=2, ensure_ascii=False) + chr(10),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
