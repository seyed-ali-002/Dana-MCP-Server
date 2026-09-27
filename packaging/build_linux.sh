#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash ./packaging/build_sidecar.sh

cd ui
npm ci
npm run build
npm run tauri build

mkdir -p ../dist/packages
cp -a src-tauri/target/release/bundle/deb/*.deb ../dist/packages/ 2>/dev/null || true
cp -a src-tauri/target/release/bundle/appimage/*.AppImage ../dist/packages/ 2>/dev/null || true
