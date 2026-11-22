# ADR-001: External MCP connectors via SuperMCP + thin Dana proxy

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Users need third-party MCP servers (e.g. Godot Editor) alongside Dana tools.
Dana already can drive SuperMCP as an aggregator. Duplicating every remote tool
implementations inside Dana would be fragile.

## Decision

1. Store user connector definitions in a **local registry** (`connectors_registry.py`).
2. **Merge** them into SuperMCP `mcpServers` config (no personal paths in git).
3. For high-value integrations (Godot), expose a **thin proxy** in Dana's FastMCP
   registry that forwards over a **single** SuperMCP SSE session.
4. Control Center **Connectors** tab manages registry + refresh via setup API.

## Consequences

- Live connectivity depends on SuperMCP + upstream server processes.
- Proxy tool names are stable for clients even if SuperMCP prefixes change
  (mapping maintained in `godot_proxy.py`).
- Concurrent SSE sessions to SuperMCP 0.1.8 must be avoided.
- Docs: `16-connectors-supermcp-godot.md`; policy: `17-documentation-policy.md`.
