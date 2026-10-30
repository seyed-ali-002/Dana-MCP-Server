#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?version required}"
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid SemVer: $VERSION" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 - "$VERSION" <<'ENDPY'
import json
import re
import sys
from pathlib import Path

version = sys.argv[1]
root = Path('.')

def rewrite_toml_version(path: Path) -> None:
    if not path.is_file():
        return
    lines = path.read_text(encoding='utf-8').splitlines()
    out = []
    seen = False
    for line in lines:
        if re.match(r'^version\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+"\s*$', line):
            if seen:
                continue
            out.append(f'version = "{version}"')
            seen = True
            continue
        out.append(line)
    if not seen:
        final = []
        inserted = False
        for line in out:
            final.append(line)
            if not inserted and line.strip() in {'[project]', '[package]'}:
                final.append(f'version = "{version}"')
                inserted = True
        out = final
    path.write_text('
'.join(out) + '
', encoding='utf-8')

def rewrite_init(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding='utf-8')
    new = re.sub(
        r'^__version__\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+"',
        f'__version__ = "{version}"',
        text,
        count=1,
        flags=re.M,
    )
    if new == text and '__version__' not in text:
        new = f'__version__ = "{version}"
' + text
    path.write_text(new, encoding='utf-8')

def rewrite_json(path: Path) -> None:
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    data['version'] = version
    path.write_text(json.dumps(data, indent=2) + '
', encoding='utf-8')

rewrite_toml_version(root / 'pyproject.toml')
rewrite_toml_version(root / 'ui' / 'src-tauri' / 'Cargo.toml')
rewrite_init(root / 'dana' / '__init__.py')
rewrite_json(root / 'ui' / 'package.json')
rewrite_json(root / 'ui' / 'src-tauri' / 'tauri.conf.json')

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
with open(root / 'pyproject.toml', 'rb') as fh:
    parsed = tomllib.load(fh)
assert parsed.get('project', {}).get('version') == version, parsed.get('project')
print(f'Set project version to {version}')
ENDPY
