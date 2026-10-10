#!/usr/bin/env bash
set -euo pipefail
# Prefer the real frozen binary if it works; otherwise fall back to python -m.
ROOT_CANDIDATES=(
  "${DANA_ROOT:-}"
  "/mnt/1CEC9AE6EC9ABA0A/Ali/MCP_Server/Dana"
  "$(dirname "$0")/../.."
  "/usr/lib/Dana"
)
export PYTHONPATH=""
for root in "${ROOT_CANDIDATES[@]}"; do
  [ -n "$root" ] || continue
  if [ -f "$root/dana/setup_service.py" ]; then
    export PYTHONPATH="$root${PYTHONPATH:+:$PYTHONPATH}"
    exec python3 -m dana.setup_service "$@"
  fi
done
# Last resort: system-installed package
if python3 -c 'import dana.setup_service' 2>/dev/null; then
  exec python3 -m dana.setup_service "$@"
fi
echo "Dana setup service could not locate the dana package." >&2
exit 1
