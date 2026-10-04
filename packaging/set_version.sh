#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?version required}"
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid SemVer: $VERSION" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 - "$VERSION" <<'PY'
import json, re, sys
from pathlib import Path
version = sys.argv[1]
root = Path(".")

def patch_text(path: Path, pattern: str, repl: str) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    new = re.sub(pattern, repl, text, count=1, flags=re.M)
    if new != text:
        path.write_text(new, encoding="utf-8")

patch_text(root / "pyproject.toml", r'^version = "[0-9]+\.[0-9]+\.[0-9]+"', f'version = "{version}"')
patch_text(root / "dana" / "__init__.py", r'^__version__ = "[0-9]+\.[0-9]+\.[0-9]+"', f'__version__ = "{version}"')
patch_text(root / "ui" / "src-tauri" / "Cargo.toml", r'^version = "[0-9]+\.[0-9]+\.[0-9]+"', f'version = "{version}"')

for rel in ("ui/package.json", "ui/src-tauri/tauri.conf.json"):
    path = root / rel
    if not path.is_file():
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

print(f"Set project version to {version}")
PY
