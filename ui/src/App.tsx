import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
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

const API = (port: number, path: string) => "http://127.0.0.1:" + port + path;

async function post(port: number, path: string) {
  const response = await fetch(API(port, path), { method: "POST" });
  return response.json();
}

function App() {
  const [port, setPort] = useState<number | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmPublic, setConfirmPublic] = useState(false);
  const [publicAcknowledged, setPublicAcknowledged] = useState(false);
  const [message, setMessage] = useState("Starting Dana setup service…");
  const [activeView, setActiveView] = useState("Setup");

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
      const next = await fetch(API(p, "/api/setup/status")).then((r) => r.json());
      setStatus(next);
      setMessage(next.message || (next.mcp_url ? "Endpoint: " + next.mcp_url : "Dana is ready for setup."));
    } catch {
      setMessage("Waiting for the local setup service…");
    }
  }

  useEffect(() => {
    let alive = true;
    invoke<number>("start_setup_service")
      .then((p) => {
        if (!alive) return;
        setPort(p);
        refresh(p);
      })
      .catch((error) => setMessage(String(error)));
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
    try {
      const result = await post(port, path);
      setMessage(String(result.message || "Step completed."));
      await refresh();
      if (result.auth_url) await openUrl(result.auth_url);
      if (result.url) setMessage("Ready: " + result.url + "/mcp");
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function continueSetup() {
    if (!status) return;
    if (!status.tailscale_installed) return run("/api/setup/install-tailscale");
    if (status.tailscale_backend.toLowerCase() !== "running") return run("/api/setup/login-tailscale");
    if (!status.dana_running) return run("/api/setup/start-dana");
    if (!status.funnel_active) { setPublicAcknowledged(false); setConfirmPublic(true); return; }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">D</div><div><strong>DANA</strong><span>MCP Control Center</span></div></div>
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
            <section className="hero glass">
              <div className="hero-glow" /><div className="hero-copy"><span className="kicker">ONE-CLICK DEPLOYMENT</span>
                <h2>Bring Dana online without the terminal.</h2>
                <p>Python runtime, Tailscale, Funnel, Dana and the public MCP endpoint are coordinated from one setup flow.</p>
                <button className="primary" disabled={busy || ready} onClick={continueSetup}>{busy ? "Working…" : ready ? "Dana is ready" : "Continue setup"}</button>
              </div><div className="hero-orb"><div className="orb-core">D</div></div>
            </section>

            <div className="grid">
              <section className="card glass"><div className="card-head"><span>01</span><strong>Tailscale</strong><b className={status?.tailscale_installed ? "state ok" : "state"}>{status?.tailscale_installed ? "INSTALLED" : "REQUIRED"}</b></div><p>Install and authenticate Tailscale. Dana opens the browser login flow automatically when required.</p><div className="meta">{status?.tailscale_backend || "Not connected"}</div></section>
              <section className="card glass"><div className="card-head"><span>02</span><strong>Dana Runtime</strong><b className={status?.dana_running ? "state ok" : "state"}>{status?.dana_running ? "ONLINE" : "PENDING"}</b></div><p>Start the local MCP service using Docker when available, with native Python as a fallback.</p><div className="meta">127.0.0.1:8765</div></section>
              <section className="card glass"><div className="card-head"><span>03</span><strong>Funnel</strong><b className={status?.funnel_active ? "state ok" : "state"}>{status?.funnel_active ? "ACTIVE" : "APPROVAL"}</b></div><p>Expose only the canonical HTTPS origin. Funnel approval is always an explicit user action.</p><div className="meta">{status?.funnel_hostname || "Not configured"}</div></section>
            </div>

            <section className="progress-card glass"><div className="progress-top"><div><span className="eyebrow">SETUP PROGRESS</span><strong>{progress}%</strong></div><span>{message}</span></div><div className="track"><div className="track-fill" style={{ width: progress + "%" }} /></div><div className="steps"><span className={status?.tailscale_installed ? "done" : ""}>Tailscale</span><span className={status?.tailscale_backend.toLowerCase() === "running" ? "done" : ""}>Authentication</span><span className={status?.dana_running ? "done" : ""}>Dana</span><span className={status?.funnel_active ? "done" : ""}>Funnel</span></div></section>
          </>
        ) : (
          <section className="empty glass"><div className="empty-icon">◈</div><h2>{activeView}</h2><p>This control-plane section is wired to the same Dana runtime. Setup is the first fully automated workflow.</p><button className="secondary" onClick={() => setActiveView("Setup")}>Back to setup</button></section>
        )}
      </main>

      {confirmPublic && <div className="modal-backdrop"><div className="modal glass"><div className="modal-icon">!</div><div className="eyebrow">PUBLIC INTERNET EXPOSURE</div><h2>Enable Tailscale Funnel?</h2><p>This publishes Dana’s HTTPS endpoint to the public internet. Tailscale may also require an administrator approval in the browser.</p><label className="confirm-line"><input type="checkbox" checked={publicAcknowledged} onChange={(e) => setPublicAcknowledged(e.target.checked)} /><span>I understand that Funnel makes the endpoint publicly reachable.</span></label><div className="modal-actions"><button className="secondary" onClick={() => setConfirmPublic(false)}>Cancel</button><button className="primary" disabled={!publicAcknowledged || busy} onClick={() => { setConfirmPublic(false); run("/api/setup/enable-funnel"); }}>Enable Funnel</button></div></div></div>}
    </div>
  );
}

export default App;