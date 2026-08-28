$ErrorActionPreference = "Stop"
$Port = if ($env:DANA_PORT) { $env:DANA_PORT } else { "8765" }

Write-Host "Starting Tailscale Funnel for Dana on localhost:$Port"
tailscale funnel --bg "http://127.0.0.1:$Port"
tailscale funnel status
