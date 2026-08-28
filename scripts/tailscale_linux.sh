#!/usr/bin/env bash
set -euo pipefail

PORT="${DANA_PORT:-8765}"

echo "Starting Tailscale Funnel for Dana on localhost:${PORT}"
tailscale funnel --bg "http://127.0.0.1:${PORT}"
tailscale funnel status
