#!/usr/bin/env bash
# Prefetch Linux AppImage helper binaries into ~/.cache/tauri (Tauri tools dir).
set -euo pipefail
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/tauri"
mkdir -p "$CACHE"
download() {
  local url="$1" out="$2"
  local i
  for i in 1 2 3 4 5; do
    echo "Download attempt $i: $url"
    if curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors -o "$out" "$url"; then
      if [[ -s "$out" ]]; then
        echo "OK: $out ($(wc -c < "$out") bytes)"
        return 0
      fi
    fi
    sleep $((i * 5))
  done
  echo "WARN: failed to download $url" >&2
  return 1
}

if [[ ! -f "$CACHE/AppRun-x86_64" ]]; then
  download "https://github.com/tauri-apps/binary-releases/releases/download/apprun-old/AppRun-x86_64" \
    "$CACHE/AppRun-x86_64" || true
  chmod +x "$CACHE/AppRun-x86_64" 2>/dev/null || true
fi
echo "Linux tauri tools cache: $CACHE"
