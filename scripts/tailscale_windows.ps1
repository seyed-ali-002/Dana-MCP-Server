$ErrorActionPreference = "Stop"
$Port = if ($env:DANA_PORT) { $env:DANA_PORT } else { "8765" }

Write-Host "Starting Tailscale Funnel for Dana on localhost:$Port"
Write-Host "First-time setup: approve Funnel in the Tailscale confirmation page if prompted."
tailscale funnel --bg $Port
tailscale funnel status
