#!/usr/bin/env python3
"""Add connection mode dropdown + Settings secondary rail."""
from pathlib import Path

t = Path("ui/src/App.tsx").read_text(encoding="utf-8")
changed = False

if "endpointMode" not in t and 'useState("Dashboard")' in t:
    t = t.replace(
        'const [view, setView] = useState("Dashboard");',
        'const [view, setView] = useState("Dashboard");\n'
        '  const [endpointMode, setEndpointMode] = useState<"all" | "local" | "public" | "supermcp">("all");',
    )
    changed = True
    print("endpointMode state")

old = '''                  <div className="clash-mode-segmented" role="group" aria-label="Routing mode">
                    <button
                      type="button"
                      className={"seg-btn" + (!status?.local_only ? " active" : "")}
                      disabled={busy}
                      onClick={async () => {
                        if (!port) return;
                        await fetch(API(port, "/api/setup/local-only"), {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ enabled: false }),
                        });
                        await refresh(port);
                      }}
                    >
                      🌐 Public Tunnel (Funnel)
                    </button>
                    <button
                      type="button"
                      className={"seg-btn" + (status?.local_only ? " active" : "")}
                      disabled={busy}
                      onClick={async () => {
                        if (!port) return;
                        await fetch(API(port, "/api/setup/local-only"), {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ enabled: true }),
                        });
                        await refresh(port);
                      }}
                    >
                      🔒 Local Only
                    </button>
                  </div>'''

new = '''                  <div className="mode-field">
                    <label className="mode-label" htmlFor="endpoint-mode">Connection mode</label>
                    <div className="dana-select-wrap">
                      <select
                        id="endpoint-mode"
                        className="dana-select"
                        disabled={busy || !port}
                        value={endpointMode}
                        onChange={async (e) => {
                          const mode = e.target.value as "all" | "local" | "public" | "supermcp";
                          setEndpointMode(mode);
                          if (!port) return;
                          if (mode === "local") {
                            await fetch(API(port, "/api/setup/local-only"), {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ enabled: true }),
                            });
                          } else {
                            await fetch(API(port, "/api/setup/local-only"), {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ enabled: false }),
                            });
                          }
                          if (mode === "supermcp" || mode === "all") {
                            try { await fetch(API(port, "/api/setup/supermcp/start"), { method: "POST" }); } catch {}
                          }
                          await refresh(port);
                        }}
                      >
                        <option value="all">All · Local + Public + SuperMCP</option>
                        <option value="local">Local only</option>
                        <option value="public">Public endpoint (Funnel)</option>
                        <option value="supermcp">SuperMCP Assistant only</option>
                      </select>
                      <span className="dana-select-caret" aria-hidden="true">▾</span>
                    </div>
                  </div>'''

if old in t:
    t = t.replace(old, new)
    changed = True
    print("mode dropdown")
elif "endpoint-mode" in t:
    print("mode already")
else:
    print("WARN mode segment not found")

if "settings-shell" not in t:
    marker = '{port && (view === "Settings" && settingsTab === "Config") && ('
    rail = '''
        {port && view === "Settings" && (
          <div className="settings-shell">
            <aside className="settings-rail" aria-label="Settings sections">
              <div className="settings-rail-title">Settings</div>
              {settingsItems.map((x) => (
                <button
                  key={x.id}
                  type="button"
                  className={"settings-rail-item" + (settingsTab === x.id ? " active" : "")}
                  onClick={() => setSettingsTab(x.id)}
                >
                  <span className="nav-icon"><NavIcon name={x.icon} /></span>
                  <span>{x.label}</span>
                </button>
              ))}
              <button type="button" className="settings-back" onClick={() => setView("Dashboard")}>
                ← Back to Dashboard
              </button>
            </aside>
            <div className="settings-main">
        '''
    if marker in t:
        t = t.replace(marker, rail + "\n        " + marker, 1)
        logs = '{port && view === "Logs" && ('
        if logs in t:
            t = t.replace(logs, "            </div>\n          </div>\n        )}\n        " + logs, 1)
        changed = True
        print("settings shell")
    else:
        print("WARN config marker missing")

if changed:
    Path("ui/src/App.tsx").write_text(t, encoding="utf-8")
    print("wrote", len(t))
else:
    print("no changes")
