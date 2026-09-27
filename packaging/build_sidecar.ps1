$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
Remove-Item -Recurse -Force ui/src-tauri/resources -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force ui/src-tauri/resources | Out-Null
python -m pip install -e ".[build]"
python -m PyInstaller --clean --noconfirm packaging/dana-agent.spec
Copy-Item dist\dana-agent.exe ui\src-tauri\resources\dana-agent.exe -Force
