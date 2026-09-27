#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUILD_VENV="$ROOT/.build-venv"
rm -rf "$BUILD_VENV"
python3 -m venv "$BUILD_VENV"
BUILD_PYTHON="$BUILD_VENV/bin/python"

rm -rf ui/src-tauri/resources
mkdir -p ui/src-tauri/resources

"$BUILD_PYTHON" -m pip install --upgrade pip
"$BUILD_PYTHON" -m pip install -e ".[build]"
"$BUILD_PYTHON" -m PyInstaller --clean --noconfirm packaging/dana-agent.spec

if [ -f dist/dana-agent ]; then
  cp dist/dana-agent ui/src-tauri/resources/dana-agent
elif [ -f dist/dana-agent.exe ]; then
  cp dist/dana-agent.exe ui/src-tauri/resources/dana-agent.exe
else
  echo "PyInstaller did not produce the Dana sidecar executable." >&2
  exit 1
fi

chmod +x ui/src-tauri/resources/dana-agent 2>/dev/null || true
