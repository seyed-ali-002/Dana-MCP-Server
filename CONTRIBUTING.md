# Contributing to Dana MCP Server

## Before you code

1. Read [`AGENTS.md`](AGENTS.md) and [`project_description_md/11-ai-guardrails.md`](project_description_md/11-ai-guardrails.md).
2. Map work to an SRS / Roadmap ID in `project_description_md/09-srs.md` and `08-development-roadmap.md`.
3. Prefer minimal diffs.

## Mandatory documentation

**Documentation after every behavioral change is mandatory.** See [`project_description_md/17-documentation-policy.md`](project_description_md/17-documentation-policy.md).

Definition of Done includes:

- Implementation + tests
- Updated SRS/Roadmap/README/CHANGELOG as applicable
- `bash scripts/sync_living_docs.sh` when living docs change
- No secrets or personal machine paths

## Development setup

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev]"   # or: pip install -e . && pip install pytest
.venv/bin/python -m pytest tests/ -q
```

UI:

```bash
cd ui && npm ci && npm run build
```

## Commit style

- `fix:` bug fix
- `feat:` user-visible feature
- `docs:` documentation only
- `chore:` build/ci/tooling
- `refactor:` no behavior change

One logical change per commit when practical.

## Security

Never commit `.env`, tokens, or credentials. Use `clean_subprocess_env()` for all subprocesses. Respect path policy.

## Pull requests

- Describe behavior change and test evidence
- Link SRS/Roadmap IDs or state «no SRS change»
- Include doc updates in the same PR
