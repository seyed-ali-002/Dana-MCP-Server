# AGENTS.md — Instructions for AI coding agents

This repository is **Dana MCP Server** (self-hosted MCP + Desktop Control Center).

## Read first (in order)

1. `project_description_md/README.md`
2. `project_description_md/12-ai-context-pack.md` — what to load for this task
3. `project_description_md/11-ai-guardrails.md` — hard no-gos
4. `project_description_md/10-ai-implementation-guide.md` — file map, patterns, PR checklist
5. `project_description_md/09-srs.md` — requirement IDs and status
6. `project_description_md/08-development-roadmap.md` — what to build next
7. `project_description_md/13-smoke-test-matrix.md` — before you claim done
8. `project_description_md/17-documentation-policy.md` — docs required every stage
9. `project_description_md/16-connectors-supermcp-godot.md` — when touching connectors/Godot

Mirrors under `docs/`: `AI_CONTEXT_PACK.md`, `AI_GUARDRAILS.md`, `AI_IMPLEMENTATION_GUIDE.md`, `SRS.md`, `DEVELOPMENT_ROADMAP.md`, `SMOKE_TEST_MATRIX.md`.

## Default priority

1. Connection stability (LOCAL/PUBLIC/session)
2. First-run / Funnel / sudo flows without loops
3. MCP contract correctness (stdout clean, schema, errors)
4. Cross-platform CLI + GUI
5. Features and UI polish

## Hard rules (summary)

- Never commit real tokens or `.env` secrets.
- Every `subprocess.run` / `Popen` must use `clean_subprocess_env()` (see `dana/subprocess_env.py`).
- Do not write logs to stdout on the MCP server path.
- Do not bypass `require_path` / path policy without an explicit product decision + SRS update.
- After user **Stop**, do not auto-start.
- Keep a **single** desktop instance; tray Quit must end the process.
- No personal hardcoded machine paths in product code.

## After every change stage (mandatory docs)

**Documentation is mandatory after each implementation/edit that changes behavior.**
See `project_description_md/17-documentation-policy.md`.

Minimum:

1. Update the relevant living doc (`09-srs.md`, `08-development-roadmap.md`, connectors doc, README, …).
2. Add a `CHANGELOG.md` entry for user-visible changes.
3. Run:

```bash
bash scripts/sync_living_docs.sh
```

Work is not Done without the matching doc update (or an explicit «no SRS/doc change» note).

## Versioning

Follow `project_description_md/06-versioning-release.md` and current `pyproject.toml` version.

## Scope control

Do not add large third-party stacks or "fun" features as release blockers. Prefer minimal diffs tied to a requirement ID (`FR-*`, `TECH-*`, `R17-*`, …).

When adding/changing MCP tools, follow `project_description_md/18-mcp-tool-quality.md`.
