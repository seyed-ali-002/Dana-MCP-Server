# Pre-download Tauri Windows bundler toolchains (WiX + NSIS) into %LOCALAPPDATA%\tauri
# so `tauri build` does not hit GitHub CDN 504 mid-bundle.
$ErrorActionPreference = "Stop"

function Get-WithRetry {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [int]$Attempts = 6
  )
  $dir = Split-Path -Parent $OutFile
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  for ($i = 1; $i -le $Attempts; $i++) {
    try {
      Write-Host "Download attempt $i/$Attempts : $Url"
      $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
      if ($curl) {
        & curl.exe -fsSL --retry 5 --retry-delay 5 --retry-all-errors -o $OutFile $Url
        if ($LASTEXITCODE -ne 0) { throw "curl exit $LASTEXITCODE" }
      } else {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 300
      }
      if ((Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 1000)) {
        Write-Host "OK: $OutFile ($((Get-Item $OutFile).Length) bytes)"
        return
      }
      throw "Downloaded file missing or too small"
    } catch {
      Write-Host "WARN: download failed ($_)"
      if ($i -eq $Attempts) { throw }
      Start-Sleep -Seconds (10 * $i)
    }
  }
}

$tauriRoot = Join-Path $env:LOCALAPPDATA "tauri"
New-Item -ItemType Directory -Force -Path $tauriRoot | Out-Null
$tmp = Join-Path $env:TEMP ("dana-tauri-tools-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

try {
  # --- WiX 3.14 (MSI) ---
  $wixDir = Join-Path $tauriRoot "WixTools314"
  $wixMarker = Join-Path $wixDir "candle.exe"
  if (-not (Test-Path $wixMarker)) {
    Write-Host "Prefetching WiX toolset into $wixDir"
    $wixZip = Join-Path $tmp "wix314-binaries.zip"
    Get-WithRetry -Url "https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip" -OutFile $wixZip
    if (Test-Path $wixDir) { Remove-Item -Recurse -Force $wixDir }
    New-Item -ItemType Directory -Force -Path $wixDir | Out-Null
    Expand-Archive -Path $wixZip -DestinationPath $wixDir -Force
    if (-not (Test-Path $wixMarker)) {
      throw "WiX extract incomplete: candle.exe not found in $wixDir"
    }
    Write-Host "WiX ready at $wixDir"
  } else {
    Write-Host "WiX already present: $wixDir"
  }

  # --- NSIS 3.13 ---
  $nsisDir = Join-Path $tauriRoot "NSIS"
  $nsisMarker = Join-Path $nsisDir "makensis.exe"
  if (-not (Test-Path $nsisMarker)) {
    Write-Host "Prefetching NSIS into $nsisDir"
    $nsisZip = Join-Path $tmp "nsis-3.13.zip"
    Get-WithRetry -Url "https://github.com/tauri-apps/binary-releases/releases/download/nsis-3.13/nsis-3.13.zip" -OutFile $nsisZip
    $nsisExtract = Join-Path $tmp "nsis-extract"
    New-Item -ItemType Directory -Force -Path $nsisExtract | Out-Null
    Expand-Archive -Path $nsisZip -DestinationPath $nsisExtract -Force
    $inner = Get-ChildItem $nsisExtract -Directory | Select-Object -First 1
    if ($null -eq $inner) { throw "NSIS zip had no directory" }
    if (Test-Path $nsisDir) { Remove-Item -Recurse -Force $nsisDir }
    Move-Item $inner.FullName $nsisDir
    if (-not (Test-Path $nsisMarker)) {
      throw "NSIS extract incomplete: makensis.exe not found in $nsisDir"
    }
    Write-Host "NSIS ready at $nsisDir"
  } else {
    Write-Host "NSIS already present: $nsisDir"
  }

  # --- nsis_tauri_utils.dll ---
  $pluginDir = Join-Path $nsisDir "Plugins\x86-unicode\additional"
  New-Item -ItemType Directory -Force -Path $pluginDir | Out-Null
  $dllPath = Join-Path $pluginDir "nsis_tauri_utils.dll"
  if (-not (Test-Path $dllPath)) {
    Write-Host "Prefetching nsis_tauri_utils.dll"
    Get-WithRetry -Url "https://github.com/tauri-apps/nsis-tauri-utils/releases/download/nsis_tauri_utils-v0.5.3/nsis_tauri_utils.dll" -OutFile $dllPath
  } else {
    Write-Host "nsis_tauri_utils.dll already present"
  }

  Write-Host "Tauri Windows toolchains prefetched under $tauriRoot"
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
