# Dana Control Center — UI/UX Pro Max Specification (FLClash Edition)

## 1. Design Philosophy & Visual Language
Inspired by **FLClash** and **Hiddify** desktop clients, Dana Control Center uses a **Dark Bento Grid** architecture with zero default browser form controls, balanced 16px/20px spatial rhythm, and a separated **Settings & Toolkit** workspace with dedicated sub-tabs.

### Color System (FLClash Dark Carbon Palette)
- **Canvas Background (`--bg`)**: `#121316`
- **Sidebar Surface (`--sidebar`)**: `#16181d`
- **Card Surface (`--surface`)**: `#1e2028`
- **Elevated / Inner Pill Surface (`--surface-2`)**: `#262934`
- **Accent Primary (`--accent`)**: `#3b82f6` (Blue) / `#22c55e` (Emerald) / `#ef4444` (Crimson)
- **Semantic Status**:
  - Running / Healthy: `#22c55e`
  - Degraded / Pending: `#f59e0b`
  - Offline / Error: `#ef4444`

---

## 2. Information Architecture

### Primary Sidebar Navigation (5 Clean Destinations)
1. **Dashboard**: FLClash-style Bento Grid overview with Scalloped Action Orb, Token Traffic Sparklines, Connection Mode selector, Service Toggles, 4 Bento status cards, and live tabbed Activity/Logs feed.
2. **Endpoints**: Detailed Local MCP, Public Tailscale Funnel, and SuperMCP Assistant (`:3006/sse`) cards with one-click copy and live handshake verification.
3. **Skills**: Skill Packs (`agency-agents`, `superpowers`, `i-have-adhd`, `ponytail`), Zero Use Computer desktop agent, and live Markdown skill preview/editor.
4. **Activity**: Full-height collapsible live stream of MCP tool calls (with `Arguments`, `Result`, `Error`, worker slot, and token breakdown) and Setup/System events.
5. **Settings (Separated Multi-Tab Workspace)**:
   - **General & Mode**: Connection Mode (`All Services`, `Local Only`, `Public Funnel Only`, `SuperMCP Assistant Only`), Desktop notifications, Sound alerts, Updates.
   - **Authentication**: Token inspection, custom token rotation, and token revocation.
   - **Environment**: Full `.env` key-value and path-list editor with critical field lock.
   - **Repair & Diagnostics**: 3-step self-healing toolkit, live endpoint probe, and terminal commands.
   - **OpenWhip & Audio**: Interactive whip boost level, volume slider (`0–100%`), mute toggle, and test crack button.
   - **Guide & About**: Interactive documentation and OAuth client instructions.

---

## 3. Connection Modes (4-Way Selector & Custom Dropdown)
Dana supports four explicit operational modes controllable from the Dashboard bar and Settings:
1. **`all` (All Services)**: Local MCP (`127.0.0.1:8765`) + Public Tailscale Funnel (`https://...:443`) + SuperMCP Proxy (`127.0.0.1:3006/sse`).
2. **`local` (Local Only)**: Local MCP server only; Tailscale Funnel and SuperMCP proxy are kept off.
3. **`public` (Public Funnel Only)**: Local MCP + Tailscale HTTPS Funnel enabled; SuperMCP proxy stopped.
4. **`supermcp` (SuperMCP Assistant Only)**: Local MCP + SuperMCP SSE/message proxy on port `3006` for browser extensions; Public Funnel disabled.
