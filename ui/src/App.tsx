import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import logo from "../src-tauri/icons/icon.png";
import "./App.css";

type Status = {
  tailscale_installed: boolean;
  tailscale_backend: string;
  tailscale_hostname: string;
  funnel_active: boolean;
  funnel_hostname: string;
  dana_running: boolean;
  mcp_url: string;
  action_required: string;
  message: string;
};

type TokenUsage = {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  operations: number;
  available: boolean;
};

type SetupLog = {
  time: string;
  level: string;
  message: string;
};


const API = (port: number, path: string) => "http://127.0.0.1:" + port + path;


function App() {
  const [port, setPort] = useState<number | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmPublic, setConfirmPublic] = useState(false);
  const [publicAcknowledged, setPublicAcknowledged] = useState(false);
  const [message, setMessage] = useState("Starting Dana setup service…");
  const [activeView, setActiveView] = useState("Setup");
  const [error, setError] = useState("");
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [logs, setLogs] = useState<SetupLog[]>([]);

  const ready = Boolean(status?.dana_running && status?.funnel_active);
  const progress = useMemo(() => {
    if (!status) return 8;
    if (!status.tailscale_installed) return 20;
    if (status.tailscale_backend.toLowerCase() !== "running") return 40;
    if (!status.dana_running) return 68;
    if (!status.funnel_active) return 82;
    return 100;
  }, [status]);

  async function refresh(p = port) {
    if (!p) return;
    try {
      const response = await fetch(API(p, "/api/setup/status"));
      const next = await response.json();
      if (!response.ok) throw new Error(next.message || next.error || `Setup service returned HTTP ${response.status}`);
      setStatus(next);
      try {
        const usageResponse = await fetch(API(p, "/api/setup/usage"));
        if (usageResponse.ok) setUsage(await usageResponse.json());
      } catch { }
      try {
        const logsResponse = await fetch(API(p, "/api/setup/logs"));
        if (logsResponse.ok) {
          const payload = await logsResponse.json();
          setLogs(Array.isArray(payload.logs) ? payload.logs : []);
        }
      } catch { }
      setMessage(next.message || (next.mcp_url ? "Endpoint: " + next.mcp_url : "Dana is ready for setup."));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMessage("Waiting for the local setup service…");
    }
  }

  useEffect(() => {
    let alive = true;
    invoke<number>("start_setup_service")
      .then((p) => {
        if (!alive) return;
        setPort(p);
        setError("");
        refresh(p);
      })
      .catch((error) => {
        const detail = error instanceof Error ? error.message : String(error);
        setError(detail.includes("Dana project root was not found")
          ? "Dana could not locate its bundled setup service. Reinstall the latest Dana package; no DANA_ROOT configuration should be required for an installed build."
          : detail);
        setMessage("Dana setup service could not be started.");
      });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!port) return;
    const timer = window.setInterval(() => refresh(), 1800);
    return () => window.clearInterval(timer);
  }, [port]);

  async function run(path: string) {
    if (!port || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(API(port, path), { method: "POST" });
      const raw = await response.text();
      let result: Record<string, unknown> = {};
      try { result = raw ? JSON.parse(raw) : {}; } catch { result = { message: raw }; }
      if (!response.ok || (result.ok === false && !result.pending)) throw new Error(String(result.message || result.error || `Setup action failed (HTTP ${response.status})`));
      setMessage(String(result.message || "Step completed."));
      await refresh();
      if (typeof result.auth_url === "string" && result.auth_url) await openUrl(result.auth_url);
      if (typeof result.url === "string" && result.url) setMessage("Ready: " + result.url.replace(/\/$/, "") + "/mcp");
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(detail);
      setMessage("Setup action failed. See the error panel below.");
    } finally {
      setBusy(false);
    }
  }

  async function continueSetup() {
    if (!status) {
      setError("Setup status is not available yet. Refreshing the local setup service…");
      await refresh();
      return;
    }
    if (!status.tailscale_installed) return run("/api/setup/install-tailscale");
    if (status.tailscale_backend.toLowerCase() !== "running") return run("/api/setup/login-tailscale");
    if (!status.dana_running) return run("/api/setup/start-dana");
    if (!status.funnel_active) { setPublicAcknowledged(false); setConfirmPublic(true); return; }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><img src={logo} alt="Dana" /></div><div><strong>DANA</strong><span>MCP Control Center</span></div></div>
        <nav>
          {["Setup", "Dashboard", "Connections", "Runtime", "Security", "Logs"].map((item) => (
            <button key={item} className={activeView === item ? "nav-item active" : "nav-item"} onClick={() => setActiveView(item)}>
              <span className="nav-dot" />{item}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><div className="tiny-status"><span className={ready ? "pulse on" : "pulse"} /> {ready ? "Online" : "Setup required"}</div><span>v0.1.0</span></div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div><div className="eyebrow">LOCAL CONTROL PLANE</div><h1>{activeView}</h1></div>
          <div className="top-actions"><div className="connection-pill"><span className={ready ? "dot on" : "dot"} /> {ready ? "Protected endpoint active" : "Configuration in progress"}</div><button className="icon-button" onClick={() => refresh()}>↻</button></div>
        </header>

        {activeView === "Setup" ? (
          <>
            {error && (
              <section className="alert-banner glass alert-error" role="alert">
                <div className="alert-icon">!</div>
                <div className="alert-copy"><strong>Setup error</strong><p>{error}</p></div>
                <div className="alert-actions">
                  <button className="secondary" onClick={() => { setError(""); refresh(); }}>Retry</button>
                  <button className="alert-close" aria-label="Dismiss error" onClick={() => setError("")}>×</button>
                </div>
              </section>
            )}


            <section className="hero glass">
              <div className="hero-glow" /><div className="hero-copy"><span className="kicker">ONE-CLICK DEPLOYMENT</span>
                <h2>Bring Dana online without the terminal.</h2>
                <p>Python runtime, Tailscale, Funnel, Dana and the public MCP endpoint are coordinated from one setup flow.</p>
                <button className="primary" disabled={busy || ready || !status} onClick={continueSetup}>{busy ? "Working…" : ready ? "Dana is ready" : !status ? "Loading setup…" : "Continue setup"}</button>
              </div><div className="hero-orb"><div className="orb-core"><img src={logo} alt="Dana" /></div></div>
            </section>

            <section className="usage-card glass"><div><span className="eyebrow">TOKEN USAGE</span><strong>{usage?.available ? usage.total_tokens.toLocaleString() : "—"}</strong><span className="usage-caption">{usage?.available ? "total recorded tokens" : "No analytics data yet"}</span></div><div className="usage-stats"><span>Input <b>{usage?.available ? usage.input_tokens.toLocaleString() : "—"}</b></span><span>Output <b>{usage?.available ? usage.output_tokens.toLocaleString() : "—"}</b></span><span>Operations <b>{usage?.available ? usage.operations.toLocaleString() : "—"}</b></span></div></section>

            <div className="grid">
              <section className="card glass"><div className="card-head"><span>01</span><strong>Tailscale</strong><b className={status?.tailscale_installed ? "state success" : "state warning"}>{status?.tailscale_installed ? "INSTALLED" : "REQUIRED"}</b></div><p>Install and authenticate Tailscale. Dana opens the browser login flow automatically when required.</p><div className="meta">{status?.tailscale_backend || "Not connected"}</div></section>
              <section className="card glass"><div className="card-head"><span>02</span><strong>Dana Runtime</strong><b className={status?.dana_running ? "state success" : "state warning"}>{status?.dana_running ? "ONLINE" : "PENDING"}</b></div><p>Start the local MCP service using Docker when available, with native Python as a fallback.</p><div className="meta">127.0.0.1:8765</div></section>
              <section className="card glass"><div className="card-head"><span>03</span><strong>Funnel</strong><b className={status?.funnel_active ? "state success" : "state warning"}>{status?.funnel_active ? "ACTIVE" : "APPROVAL"}</b></div><p>Expose only the canonical HTTPS origin. Funnel approval is always an explicit user action.</p><div className="meta">{status?.funnel_hostname || "Not configured"}</div></section>
            </div>

            <section className="progress-card glass"><div className="progress-top"><div><span className="eyebrow">SETUP PROGRESS</span><strong>{progress}%</strong></div><span>{message}</span></div><div className="track"><div className="track-fill" style={{ width: progress + "%" }} /></div><div className="steps"><span className={status?.tailscale_installed ? "done" : ""}>Tailscale</span><span className={status?.tailscale_backend.toLowerCase() === "running" ? "done" : ""}>Authentication</span><span className={status?.dana_running ? "done" : ""}>Dana</span><span className={status?.funnel_active ? "done" : ""}>Funnel</span></div></section>
          </>
        ) : activeView === "Logs" ? (
          <section className="logs-panel glass">
            <div className="logs-head"><div><span className="eyebrow">SETUP & REGISTRATION LOG</span><h2>What Dana is doing</h2></div><button className="secondary" onClick={() => refresh()}>Refresh</button></div>
            <p className="logs-description">Every setup action, authentication attempt, Funnel approval and runtime launch is recorded here so failures are visible instead of silently stopping.</p>
            <div className="log-list">
              {logs.length === 0 ? <div className="log-empty">No setup events recorded yet.</div> : logs.slice().reverse().map((entry, index) => (
                <div className={"log-row log-" + entry.level} key={entry.time + entry.message + index}>
                  <span className="log-time">{entry.time}</span><span className={"log-level " + entry.level}>{entry.level.toUpperCase()}</span><span className="log-message">{entry.message}</span>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="empty glass"><div className="empty-icon">◈</div><h2>{activeView}</h2><p>This control-plane section is wired to the same Dana runtime. Setup is the first fully automated workflow.</p><button className="secondary" onClick={() => setActiveView("Setup")}>Back to setup</button></section>
        )}
      </main>

      {confirmPublic && <div className="modal-backdrop"><div className="modal glass"><div className="modal-icon">!</div><div className="eyebrow">PUBLIC INTERNET EXPOSURE</div><h2>Enable Tailscale Funnel?</h2><p>This publishes Dana’s HTTPS endpoint to the public internet. Tailscale may also require an administrator approval in the browser.</p><label className="confirm-line"><input type="checkbox" checked={publicAcknowledged} onChange={(e) => setPublicAcknowledged(e.target.checked)} /><span>I understand that Funnel makes the endpoint publicly reachable.</span></label><div className="modal-actions"><button className="secondary" onClick={() => setConfirmPublic(false)}>Cancel</button><button className="primary" disabled={!publicAcknowledged || busy} onClick={() => { setConfirmPublic(false); run("/api/setup/enable-funnel"); }}>Enable Funnel</button></div></div></div>}
    </div>
  );
}

export default App;