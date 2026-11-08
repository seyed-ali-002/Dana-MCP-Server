#!/usr/bin/env bash
# Sync living documents from project_description_md/ into docs/ mirrors.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/project_description_md"
DST="$ROOT/docs"
mkdir -p "$DST"

copy_pair() {
  local src_name="$1"
  local dst_name="$2"
  if [[ -f "$SRC/$src_name" ]]; then
    cp "$SRC/$src_name" "$DST/$dst_name"
    echo "synced $dst_name"
  else
    echo "skip missing $src_name" >&2
  fi
}

copy_pair "08-development-roadmap.md" "DEVELOPMENT_ROADMAP.md"
copy_pair "09-srs.md" "SRS.md"
copy_pair "10-ai-implementation-guide.md" "AI_IMPLEMENTATION_GUIDE.md"
copy_pair "11-ai-guardrails.md" "AI_GUARDRAILS.md"
copy_pair "12-ai-context-pack.md" "AI_CONTEXT_PACK.md"

cat > "$DST/README.md" << 'EOF'
# Dana docs (living mirrors)

Canonical numbered sources live in `project_description_md/`.
After editing those files, run:

```bash
bash scripts/sync_living_docs.sh
```

| Mirror | Canonical |
|--------|-----------|
| [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) | `08-development-roadmap.md` |
| [SRS.md](SRS.md) | `09-srs.md` |
| [AI_IMPLEMENTATION_GUIDE.md](AI_IMPLEMENTATION_GUIDE.md) | `10-ai-implementation-guide.md` |
| [AI_GUARDRAILS.md](AI_GUARDRAILS.md) | `11-ai-guardrails.md` |
| [AI_CONTEXT_PACK.md](AI_CONTEXT_PACK.md) | `12-ai-context-pack.md` |

Also see root [AGENTS.md](../AGENTS.md) for AI coding agents.
EOF

echo "done"
