#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
rm -rf ui/src-tauri/resources
mkdir -p ui/src-tauri/resources
python3 -m pip install -e ".[build]"
python3 -m PyInstaller --clean --noconfirm packaging/dana-agent.spec
if [ -f dist/dana-agent/dana-agent ]; then
  cp dist/dana-agent/dana-agent ui/src-tauri/resources/dana-agent
elif [ -f dist/dana-agent.exe ]; then
  cp dist/dana-agent.exe ui/src-tauri/resources/dana-agent.exe
fi
