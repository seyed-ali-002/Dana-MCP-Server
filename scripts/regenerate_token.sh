#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/regenerate_token.py
printf '%s\n' 'Restart Dana after regenerating the token.'
