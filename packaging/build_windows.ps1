$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

# Optional Authenticode signing when GitHub secrets are mapped to env vars.
if ($env:WINDOWS_CERTIFICATE_BASE64 -and $env:WINDOWS_CERTIFICATE_PASSWORD) {
  Write-Host "Importing Windows code-signing certificate…"
  $certPath = Join-Path $env:TEMP "dana-codesign.pfx"
  [IO.File]::WriteAllBytes($certPath, [Convert]::FromBase64String($env:WINDOWS_CERTIFICATE_BASE64))
  $secure = ConvertTo-SecureString -String $env:WINDOWS_CERTIFICATE_PASSWORD -AsPlainText -Force
  Import-PfxCertificate -FilePath $certPath -CertStoreLocation Cert:\CurrentUser\My -Password $secure | Out-Null
  $env:TAURI_SIGNING_PRIVATE_KEY = $env:TAURI_SIGNING_PRIVATE_KEY
  # Tauri Windows signing uses these env vars when set:
  $env:WINDOWS_CERTIFICATE = $certPath
  $env:WINDOWS_CERTIFICATE_PASSWORD = $env:WINDOWS_CERTIFICATE_PASSWORD
}

./packaging/build_sidecar.ps1

Set-Location ui
npm ci
npm run build
npm run tauri build

Write-Host "Dana GUI bundles are in ui/src-tauri/target/release/bundle"
