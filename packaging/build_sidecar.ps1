$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$BuildVenv = Join-Path $Root ".build-venv"
if (Test-Path $BuildVenv) {
    Remove-Item -Recurse -Force $BuildVenv
}
python -m venv $BuildVenv
$BuildPython = Join-Path $BuildVenv "Scripts\python.exe"

Remove-Item -Recurse -Force ui/src-tauri/resources -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force ui/src-tauri/resources | Out-Null

& $BuildPython -m pip install --upgrade pip
& $BuildPython -m pip install -e ".[build]"
& $BuildPython -m PyInstaller --clean --noconfirm packaging/dana-agent.spec

$Sidecar = Join-Path $Root "dist\dana-agent.exe"
if (-not (Test-Path $Sidecar)) {
    throw "PyInstaller did not produce the Dana sidecar executable."
}
Copy-Item $Sidecar ui\src-tauri\resources\dana-agent.exe -Force
