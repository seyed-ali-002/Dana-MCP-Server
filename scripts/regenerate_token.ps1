$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python scripts/regenerate_token.py
Write-Host "Restart Dana after regenerating the token."
