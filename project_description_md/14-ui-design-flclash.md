# Dana UI Design Spec — FLClash-inspired (v1.8)

> Living document. Update when screens or navigation change.

## 1. Design goals

1. **Look & feel of a real desktop network app** (FlClash / Hiddify family): dense information cards, icon sidebar, soft surfaces, no browser-default controls.
2. **Primary workflow first**: start/stop Dana, see connection health, copy endpoints — one glance on Dashboard.
3. **Secondary complexity isolated**: Config, Skills, Repair, Usage, Help live under a separate **Settings** area (like “Tools / Settings” in FlClash), not competing with the main ops loop.
4. **Zero unstyled controls**: every button, select, input, toggle, table, and scrollbar uses Dana tokens (no native OS chrome).
5. **Readable density**: 14–16px body, 16–18px titles; consistent 12/16/20/24 spacing scale.

## 2. Information architecture

### Primary shell (always visible)

| Nav id | Label | Role |
|--------|--------|------|
| `Dashboard` | Dashboard | Status hero, activate, health layers, endpoint cards, connection mode |
| `Network` | Network | Tailscale / Funnel / SuperMCP controls, connection tests |
| `Logs` | Logs | Setup log + tool activity (stacked, collapsible detail) |
| `Settings` | Settings | Hub that opens secondary navigation |

### Settings hub (secondary app section)

| Sub-id | Label | Role |
|--------|--------|------|
| `Config` | Configuration | Env keys, auth token, accent/theme |
| `Skills` | Skills | Skill packs path / upload / enable |
| `Repair` | Repair | Recover, reinstall funnel, reset preferences |
| `Usage` | Usage | Token charts, session totals, recent tool events |
| `Help` | Guide | Step-by-step connect + SuperMCP + troubleshooting TOC |

Navigation model: clicking **Settings** switches the main pane to a settings layout with its own left sub-rail. Back affordance returns to last primary view.

## 3. Connection modes (dropdown)

| Mode | Behavior |
|------|----------|
| `all` | Local MCP + public funnel endpoint + SuperMCP proxy (default) |
| `local` | Local MCP only; skip funnel/public |
| `public` | Prefer public funnel endpoint; still keep local for health |
| `supermcp` | Focus SuperMCP SSE for browser extensions; keep local upstream |

UI: custom styled select (not native OS menu). Persist via `/api/setup/local-only` + SuperMCP start/stop.

## 4. Visual system

Dark tokens: `--bg #0f1115`, `--chrome #14171d`, `--card #1a1e26`, `--text #e8eaed`, `--muted #8b93a7`, `--ok #3dd68c`.
Sidebar 84px icon rail. Cards 16px radius. Spacing scale 4·8·12·16·20·24·32.

## 5. Logo

Abstract D formed by node + link arc (MCP bridge). Files: `ui/src/assets/dana-logo.svg|.png`.

## 6. Acceptance

- [ ] No native unstyled controls
- [ ] Settings is separate section with sub-nav
- [ ] Connection mode dropdown works
- [ ] Logo in sidebar
- [ ] MCP connectivity unaffected by pure UI change
