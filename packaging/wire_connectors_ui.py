#!/usr/bin/env python3
"""Wire ConnectorsPage into ui/src/App.tsx (idempotent)."""
from __future__ import annotations
from pathlib import Path

p = Path("ui/src/App.tsx")
t = p.read_text(encoding="utf-8")
changed = False

if "ConnectorsPage" not in t:
    needle = 'import WhipOverlay from "./WhipOverlay";'
    if needle in t:
        t = t.replace(needle, needle + '\nimport ConnectorsPage from "./ConnectorsPage";', 1)
        changed = True

if "Connectors & Tools" not in t:
    old = '{ id: "Skills", label: "Skills & Agents", icon: "skills" },'
    new = old + '\n    { id: "Connectors", label: "Connectors & Tools", icon: "connectors" },'
    if old in t:
        t = t.replace(old, new, 1)
        changed = True
    ot = 'id: "Setup" | "Control" | "Skills" | "Logs"'
    nt = 'id: "Setup" | "Control" | "Skills" | "Connectors" | "Logs"'
    if ot in t:
        t = t.replace(ot, nt, 1)
        changed = True

if 'name === "connectors"' not in t:
    idx = t.find('if (name === "help")')
    if idx > 0:
        icon = (
            '    if (name === "connectors")\n'
            '      return (\n'
            '        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">\n'
            '          <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />\n'
            '          <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.7" />\n'
            '          <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.7" />\n'
            '          <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.7" />\n'
            '          <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.7" />\n'
            '        </svg>\n'
            '      );\n'
        )
        t = t[:idx] + icon + t[idx:]
        changed = True

if 'view === "Connectors"' not in t:
    marker = '{port && view === "Logs"'
    idx = t.find(marker)
    if idx > 0:
        line_start = t.rfind("\n", 0, idx) + 1
        insert = (
            '      {port && view === "Connectors" && (\n'
            '        <ConnectorsPage port={port} setMessage={setMessage} setError={setError} />\n'
            '      )}\n\n'
        )
        t = t[:line_start] + insert + t[line_start:]
        changed = True

if changed:
    p.write_text(t, encoding="utf-8")
    print("App.tsx updated")
else:
    print("App.tsx already wired")
