$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

./packaging/build_sidecar.ps1

Set-Location ui
npm install
npm run build
npm run tauri build

Write-Host "Dana GUI bundles are in ui/src-tauri/target/release/bundle"
