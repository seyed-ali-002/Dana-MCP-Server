#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash ./packaging/prefetch_tauri_tools.sh || true
bash ./packaging/build_sidecar.sh

cd ui
npm ci
npm run build

tauri_ok=0
for attempt in 1 2 3; do
  echo "tauri build attempt ${attempt}/3…"
  if npm run tauri build; then
    tauri_ok=1
    break
  fi
  if [[ -n "$(find src-tauri/target/release/bundle/deb -name '*.deb' 2>/dev/null | head -1)" ]]; then
    echo "Warning: full tauri bundle failed (often AppImage CDN 504), but .deb is present — continuing."
    tauri_ok=1
    break
  fi
  echo "tauri build failed; waiting 25s before retry…"
  sleep 25
done

if [[ "$tauri_ok" -ne 1 ]]; then
  echo "tauri build failed after retries and no .deb was produced." >&2
  exit 1
fi

mkdir -p ../dist/packages
cp -a src-tauri/target/release/bundle/deb/*.deb ../dist/packages/ 2>/dev/null || true
cp -a src-tauri/target/release/bundle/rpm/*.rpm ../dist/packages/ 2>/dev/null || true
cp -a src-tauri/target/release/bundle/appimage/*.AppImage ../dist/packages/ 2>/dev/null || true
