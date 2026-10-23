# Code signing (Windows / macOS)

Unsigned installers trigger OS malware / Gatekeeper warnings. Dana CI can sign builds when secrets are configured.

## Windows (SmartScreen)

1. Obtain an Authenticode code-signing certificate (OV or EV).
2. Export as `.pfx` and base64-encode it.
3. Add GitHub Actions secrets:
   - `WINDOWS_CERTIFICATE_BASE64` — base64 of the `.pfx`
   - `WINDOWS_CERTIFICATE_PASSWORD` — PFX password
4. When present, `packaging/build_windows.ps1` imports the cert and Tauri signs MSI/EXE.

Until a certificate is available, users can install via:
- Right-click installer → Properties → Unblock (if present)
- Or SmartScreen → More info → Run anyway

## macOS (Gatekeeper)

1. Apple Developer account + Developer ID Application certificate.
2. Add GitHub Actions secrets:
   - `APPLE_CERTIFICATE_BASE64` — base64 of the `.p12`
   - `APPLE_CERTIFICATE_PASSWORD`
   - `APPLE_ID` / `APPLE_TEAM_ID` / `APPLE_APP_SPECIFIC_PASSWORD` for notarization
3. When present, `packaging/build_macos.sh` signs and notarizes the app/DMG.

Until notarized, users can open via:
- System Settings → Privacy & Security → Open Anyway
- Or: `xattr -dr com.apple.quarantine /Applications/Dana.app`

## Linux

`.deb` / AppImage do not need Apple/Microsoft signing. Optional GPG package signing can be added later.
