# AGENTS.md — Instructions for AI coding agents

This repository is **Dana MCP Server** (self-hosted MCP + optional Tailscale Funnel + Desktop UI).

## Read first

1. [`project_description_md/11-ai-guardrails.md`](project_description_md/11-ai-guardrails.md)
2. [`project_description_md/10-ai-implementation-guide.md`](project_description_md/10-ai-implementation-guide.md)
3. [`project_description_md/12-ai-context-pack.md`](project_description_md/12-ai-context-pack.md)
4. Task-relevant sections of [`09-srs.md`](project_description_md/09-srs.md) and [`08-development-roadmap.md`](project_description_md/08-development-roadmap.md)

Mirrors also exist under `docs/` (run `scripts/sync_living_docs.sh` after editing living docs).

## Non-negotiables

- Do not commit secrets or real auth tokens.
- Every external `subprocess.run` / `Popen` must use `clean_subprocess_env()` from `dana/subprocess_env.py`.
- Do not write logs or prints to stdout on the MCP path; use stderr / file logging.
- Respect MCP result contracts (`dana/mcp_result_format.py`); mismatched `outputSchema` breaks clients (e.g. DeepSeek).
- Manual **Stop** must not silently auto-start again.
- Prefer minimal, reviewable diffs tied to an SRS/Roadmap ID.

## After behavioral changes

Update `project_description_md/09-srs.md` (and roadmap status when completing a milestone), then run:

```bash
bash scripts/sync_living_docs.sh
```

## Default product priority

Connection reliability and first-run setup on Linux / Windows / macOS beat cosmetic or fun features.
