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
  $env:WINDOWS_CERTIFICATE = $certPath
  $env:WINDOWS_CERTIFICATE_PASSWORD = $env:WINDOWS_CERTIFICATE_PASSWORD
}

./packaging/build_sidecar.ps1

Set-Location ui
npm ci
npm run build

# WiX toolset is downloaded from GitHub releases; transient 504s are common.
$ok = $false
for ($i = 1; $i -le 3; $i++) {
  Write-Host "tauri build attempt $i/3…"
  npm run tauri build
  if ($LASTEXITCODE -eq 0) {
    $ok = $true
    break
  }
  $msi = Get-ChildItem "src-tauri/target/release/bundle" -Recurse -Filter *.msi -ErrorAction SilentlyContinue
  $nsis = Get-ChildItem "src-tauri/target/release/bundle" -Recurse -Filter *.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'bundle' }
  if ($msi -or $nsis) {
    Write-Host "Warning: tauri reported failure but installer artifacts exist — continuing."
    $ok = $true
    break
  }
  Write-Host "tauri build failed; waiting 25s before retry…"
  Start-Sleep -Seconds 25
}
if (-not $ok) {
  throw "tauri build failed after 3 attempts (WiX/CDN download may be unavailable)."
}

Write-Host "Dana GUI bundles are in ui/src-tauri/target/release/bundle"
