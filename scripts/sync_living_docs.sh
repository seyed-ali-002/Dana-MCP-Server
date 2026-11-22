#!/usr/bin/env bash
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
    echo "synced $src_name -> docs/$dst_name"
  else
    echo "skip missing $src_name" >&2
  fi
}

copy_pair "08-development-roadmap.md" "DEVELOPMENT_ROADMAP.md"
copy_pair "09-srs.md" "SRS.md"
copy_pair "10-ai-implementation-guide.md" "AI_IMPLEMENTATION_GUIDE.md"
copy_pair "11-ai-guardrails.md" "AI_GUARDRAILS.md"
copy_pair "12-ai-context-pack.md" "AI_CONTEXT_PACK.md"
copy_pair "13-smoke-test-matrix.md" "SMOKE_TEST_MATRIX.md"
copy_pair "16-connectors-supermcp-godot.md" "CONNECTORS_SUPERMCP_GODOT.md"
copy_pair "17-documentation-policy.md" "DOCUMENTATION_POLICY.md"

cat > "$DST/README.md" << 'EOF'
# Dana docs (mirrors)

Canonical numbered documents live under `project_description_md/`.

| File | Canonical |
|------|-----------|
| [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) | `08-development-roadmap.md` |
| [SRS.md](SRS.md) | `09-srs.md` |
| [AI_IMPLEMENTATION_GUIDE.md](AI_IMPLEMENTATION_GUIDE.md) | `10-ai-implementation-guide.md` |
| [AI_GUARDRAILS.md](AI_GUARDRAILS.md) | `11-ai-guardrails.md` |
| [AI_CONTEXT_PACK.md](AI_CONTEXT_PACK.md) | `12-ai-context-pack.md` |
| [SMOKE_TEST_MATRIX.md](SMOKE_TEST_MATRIX.md) | `13-smoke-test-matrix.md` |
| [CONNECTORS_SUPERMCP_GODOT.md](CONNECTORS_SUPERMCP_GODOT.md) | `16-connectors-supermcp-godot.md` |
| [DOCUMENTATION_POLICY.md](DOCUMENTATION_POLICY.md) | `17-documentation-policy.md` |
| [adr/](adr/) | Architecture Decision Records |

Also see [AGENTS.md](../AGENTS.md), [CONTRIBUTING.md](../CONTRIBUTING.md), [CHANGELOG.md](../CHANGELOG.md).

**Documentation after every behavioral change is mandatory** — see DOCUMENTATION_POLICY.md.

```bash
bash scripts/sync_living_docs.sh
```
EOF

echo "done."
