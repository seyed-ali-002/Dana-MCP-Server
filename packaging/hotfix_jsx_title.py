#!/usr/bin/env python3
"""One-shot fix: close unclosed JSX title attribute in ui/src/App.tsx."""
from pathlib import Path

p = Path("ui/src/App.tsx")
t = p.read_text(encoding="utf-8")
old = "{url || \"\"" + ">"
new = "{url || \"\"" + "}>"
if old not in t:
    if new in t or ("title={url || \"\"}>{url" in t):
        print("already fixed")
        raise SystemExit(0)
    raise SystemExit(f"pattern not found: {old!r}")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("fixed App.tsx JSX title attribute")

# Optional: mark version
for rel in ("dana/__init__.py", "pyproject.toml", "ui/package.json"):
    path = Path(rel)
    if path.exists():
        txt = path.read_text(encoding="utf-8")
        if "1.7.1" in txt:
            path.write_text(txt.replace("1.7.1", "1.7.2"), encoding="utf-8")
            print("bumped", rel)
