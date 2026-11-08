$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

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

# Prefetch WiX + NSIS into %LOCALAPPDATA%\tauri so Tauri skips live GitHub downloads.
& "$Root\packaging\prefetch_tauri_tools.ps1"

./packaging/build_sidecar.ps1

Set-Location ui
npm ci
npm run build

$ok = $false
for ($i = 1; $i -le 2; $i++) {
  Write-Host "tauri build attempt $i/2…"
  npm run tauri build
  if ($LASTEXITCODE -eq 0) {
    $ok = $true
    break
  }
  $msi = Get-ChildItem "src-tauri/target/release/bundle" -Recurse -Filter *.msi -ErrorAction SilentlyContinue
  $nsis = Get-ChildItem "src-tauri/target/release/bundle" -Recurse -Filter *.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'nsis|bundle' -and $_.Name -notmatch '^ui\.exe$' }
  if ($msi -or $nsis) {
    Write-Host "Warning: tauri reported failure but installer artifacts exist — continuing."
    $ok = $true
    break
  }
  Write-Host "tauri build failed; re-prefetch tools and retry…"
  & "$Root\packaging\prefetch_tauri_tools.ps1"
  Start-Sleep -Seconds 10
}
if (-not $ok) {
  throw "tauri build failed after prefetch + retries (WiX/NSIS tools unavailable)."
}

Write-Host "Dana GUI bundles are in ui/src-tauri/target/release/bundle"
