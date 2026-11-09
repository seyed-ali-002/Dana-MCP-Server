#!/usr/bin/env python3
"""Surgical SuperMCP upgrades: macOS data dir, full tool manifest, progressive default."""
from pathlib import Path

p = Path("dana/supermcp.py")
t = p.read_text(encoding="utf-8")
changed = False

old_data = """def _data_dir() -> Path:
    if os.name == \"nt\":
        base = Path(os.environ.get(\"APPDATA\") or (Path.home() / \"AppData\" / \"Roaming\"))
    else:
        base = Path(os.environ.get(\"XDG_CONFIG_HOME\") or (Path.home() / \".config\"))
    path = base / \"dana\" / \"supermcp\"
    path.mkdir(parents=True, exist_ok=True)
    return path"""

new_data = """def _data_dir() -> Path:
    if os.name == \"nt\":
        base = Path(os.environ.get(\"APPDATA\") or (Path.home() / \"AppData\" / \"Roaming\"))
    elif os.uname().sysname.lower() == \"darwin\":
        base = Path.home() / \"Library\" / \"Application Support\"
    else:
        base = Path(os.environ.get(\"XDG_CONFIG_HOME\") or (Path.home() / \".config\"))
    path = base / \"dana\" / \"supermcp\"
    path.mkdir(parents=True, exist_ok=True)
    return path"""

if old_data in t:
    t = t.replace(old_data, new_data)
    changed = True
    print("data_dir macOS")

if 'shutil.which("node")' in t and "node.exe" not in t:
    t = t.replace('return shutil.which("node")', 'return shutil.which("node") or shutil.which("node.exe")')
    changed = True
    print("node.exe")

if "def generate_full_tool_manifest" not in t:
    inject = '''
def _manifest_file() -> Path:
    return _data_dir() / "dana-tools.json"


def generate_full_tool_manifest() -> Path:
    """Export every registered Dana tool into the SuperMCP data dir."""
    target = _manifest_file()
    try:
        from .server import mcp
        from .tools.tool_catalog import enrich

        manager = getattr(mcp, "_tool_manager", None)
        raw_tools: list = []
        if manager is not None:
            bucket = getattr(manager, "_tools", None)
            if isinstance(bucket, dict):
                raw_tools = sorted(bucket.values(), key=lambda tool: getattr(tool, "name", ""))
            elif hasattr(manager, "list_tools"):
                raw_tools = sorted(manager.list_tools(), key=lambda tool: getattr(tool, "name", ""))

        items: list = []
        for tool in raw_tools:
            try:
                items.append(enrich(tool))
            except Exception:
                items.append({
                    "name": getattr(tool, "name", "unknown"),
                    "canonical_name": getattr(tool, "name", "unknown"),
                    "category": "general",
                    "description": (getattr(tool, "description", "") or "").strip(),
                    "input_schema": getattr(tool, "parameters", {}) or {},
                })
        payload = {
            "count": len(items),
            "categories": sorted({str(x.get("category") or "general") for x in items}),
            "tools": items,
        }
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    except Exception:
        pass
    return target

'''
    marker = 'def _log_file() -> Path:\n    return _data_dir() / "proxy.log"\n'
    if marker in t:
        t = t.replace(marker, marker + "\n" + inject)
        changed = True
        print("manifest fn")

old_w = 'if tool_manifest and tool_manifest.is_file():\n        server["toolManifest"] = str(tool_manifest)'
new_w = '''if tool_manifest and tool_manifest.is_file():
        server["toolManifest"] = str(tool_manifest)
    else:
        try:
            generated = generate_full_tool_manifest()
            if generated.is_file():
                server["toolManifest"] = str(generated)
        except Exception:
            pass'''
if old_w in t:
    t = t.replace(old_w, new_w, 1)
    changed = True
    print("write_config manifest")

if changed:
    p.write_text(t, encoding="utf-8")
    print("wrote supermcp")
else:
    print("supermcp no changes")

op = Path("dana/tools/optimization.py")
if op.exists():
    ot = op.read_text(encoding="utf-8")
    if 'DANA_PROGRESSIVE_TOOLS", "1"' in ot:
        ot = ot.replace('DANA_PROGRESSIVE_TOOLS", "1"', 'DANA_PROGRESSIVE_TOOLS", "0"', 1)
        ot2 = ot.replace(
            '.strip().lower() not in {"0", "false", "no", "off"}',
            '.strip().lower() in {"1", "true", "yes", "on"}',
            1,
        )
        op.write_text(ot2 if ot2 != ot else ot, encoding="utf-8")
        print("optimization progressive")
    else:
        print("optimization already")
