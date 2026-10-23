#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Optional Developer ID signing + notarization when secrets are present.
if [[ -n "${APPLE_CERTIFICATE_BASE64:-}" && -n "${APPLE_CERTIFICATE_PASSWORD:-}" ]]; then
  echo "Importing Apple Developer ID certificate…"
  CERT_PATH="$(mktemp /tmp/dana-apple-cert.XXXXXX.p12)"
  echo "$APPLE_CERTIFICATE_BASE64" | base64 --decode > "$CERT_PATH"
  KEYCHAIN="$(mktemp -d /tmp/dana-keychain.XXXXXX)/codesign.keychain-db"
  KEYCHAIN_PW="$(openssl rand -base64 24)"
  security create-keychain -p "$KEYCHAIN_PW" "$KEYCHAIN"
  security set-keychain-settings -lut 21600 "$KEYCHAIN"
  security unlock-keychain -p "$KEYCHAIN_PW" "$KEYCHAIN"
  security import "$CERT_PATH" -P "$APPLE_CERTIFICATE_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN"
  security list-keychains -d user -s "$KEYCHAIN" $(security list-keychains -d user | sed s/\"//g)
  security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PW" "$KEYCHAIN" >/dev/null
  export KEYCHAIN_PATH="$KEYCHAIN"
fi

bash ./packaging/build_sidecar.sh

cd ui
npm ci
npm run build
npm run tauri build

# Notarize DMG when Apple ID secrets are configured.
if [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]]; then
  shopt -s nullglob
  for dmg in src-tauri/target/release/bundle/dmg/*.dmg; do
    echo "Notarizing $(basename "$dmg")…"
    xcrun notarytool submit "$dmg" \
      --apple-id "$APPLE_ID" \
      --team-id "$APPLE_TEAM_ID" \
      --password "$APPLE_APP_SPECIFIC_PASSWORD" \
      --wait || true
    xcrun stapler staple "$dmg" || true
  done
fi

mkdir -p ../dist/packages
cp -a src-tauri/target/release/bundle/dmg/*.dmg ../dist/packages/ 2>/dev/null || true
