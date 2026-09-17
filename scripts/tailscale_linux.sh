#!/usr/bin/env bash
set -euo pipefail

PORT="${DANA_PORT:-8765}"


echo "Starting Tailscale Funnel for Dana on localhost:${PORT}"
echo "First-time setup: approve Funnel in the Tailscale confirmation page if prompted."
tailscale funnel --bg "${PORT}"
tailscale funnel status
