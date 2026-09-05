#!/usr/bin/env bash
set -euo pipefail

PORT="${DANA_PORT:-8765}"

TOKEN="${DANA_AUTH_TOKEN:?DANA_AUTH_TOKEN is required}"

echo "Starting Tailscale Funnel for Dana on localhost:${PORT} via HTTPS 443"
tailscale funnel --https=443 --set-path="/${TOKEN}" --yes --bg "http://127.0.0.1:${PORT}"
tailscale funnel status
