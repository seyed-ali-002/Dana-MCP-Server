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
  local_mcp_url: string;
  public_mcp_url: string;
  auth_token: string;
  action_required: string;
  message: string;
};
type SetupLog = { time: string; level: string; message: string };
type DownloadState = {
  active: boolean;
  paused: boolean;
  cancelled: boolean;
  downloaded: number;
  total: number;
  speed: number;
  name: string;
  message: string;
  source?: string;
  attempt?: number;
  attempts_total?: number;
  errors?: string[];
};
type Config = {
  values: Record<string, string>;
  defaults: Record<string, string>;
  auth_token: string;
  auth_token_configured: boolean;
  keys: string[];
};
type ConnectionTest = {
  ok: boolean;
  checks: Array<{ name: string; url: string; ok: boolean; status?: number; error?: string }>;
};
type AuthFlow = { pending: boolean; kind: string; auth_url: string; message: string };
type ToolEvent = {
  time: string;
  tool: string;
  worker: string;
  number: number;
  duration_ms: number;
  input: number;
  output: number;
  success: boolean;
  source: string;
};

const API = (p: number, path: string) => "http://127.0.0.1:" + p + path;
const APP_VERSION =
  typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.1.1";

const bytes = (n: number) => {
  if (!n) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let x = n;
  while (x >= 1024 && i < 3) {
    x /= 1024;
    i++;
  }
  return x.toFixed(i ? 1 : 0) + " " + u[i];
};
const speed = (n: number) => (n ? bytes(n) + "/s" : "—");

/** Resolve setup API port from Tauri, bootstrap, or URL query (web fallback). */
async function resolveSetupPort(): Promise<number> {
  // 1) Explicit query string from dana gui --web / browser fallback
  try {
    const q = new URLSearchParams(window.location.search).get("setupPort");
    if (q) {
      const n = Number(q);
      if (Number.isFinite(n) && n > 0) return n;
    }
  } catch {
    /* ignore */
  }
  // 2) Injected by dana.gui web launcher
  const injected = (window as unknown as { __DANA_SETUP_PORT__?: number }).__DANA_SETUP_PORT__;
  if (typeof injected === "number" && injected > 0) return injected;

  // 3) Tauri invoke (desktop package / tauri dev)
  return invoke<number>("start_setup_service");
}

async function openExternal(url: string) {
  try {
    await openUrl(url);
  } catch {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

function App() {
  const [port, setPort] = useState<number | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("Setup");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("Starting Dana setup service…");
  const [logs, setLogs] = useState<SetupLog[]>([]);
  const [download, setDownload] = useState<DownloadState | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [token, setToken] = useState("");
  const [securityBusy, setSecurityBusy] = useState(false);
  const [connectionTest, setConnectionTest] = useState<ConnectionTest | null>(null);
  const [testing, setTesting] = useState(false);
  const [confirmPublic, setConfirmPublic] = useState(false);
  const [ack, setAck] = useState(false);
  const [copied, setCopied] = useState("");
  const [authFlow, setAuthFlow] = useState<AuthFlow | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [bootFailed, setBootFailed] = useState(false);
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [errorLogs, setErrorLogs] = useState<SetupLog[]>([]);

  const progress = useMemo(() => {
    if (!status) return 8;
    if (!status.tailscale_installed) return 20;
    if (status.tailscale_backend.toLowerCase() !== "running") return 40;
    if (!status.dana_running) return 68;
    if (!status.funnel_active) return 82;
    return 100;
  }, [status]);
  const ready = !!status?.dana_running;
  const localAddr = useMemo(() => {
    try {
      if (status?.local_mcp_url) {
        const u = new URL(status.local_mcp_url);
        return u.host;
      }
    } catch {
      /* ignore */
    }
    return "127.0.0.1:8765";
  }, [status?.local_mcp_url]);

  async function refresh(p = port, quiet = false): Promise<Status | null> {
    if (!p) return null;
    try {
      const r = await fetch(API(p, "/api/setup/status"));
      const x = await r.json();
      if (!r.ok) throw Error(x.message || x.error);
      setStatus(x);
      setMessage(x.message || "");
      const l = await fetch(API(p, "/api/setup/logs"));
      if (l.ok) {
        const y = await l.json();
        setLogs(y.logs || []);
        setErrorLogs(y.errors || (y.logs || []).filter((e: SetupLog) => e.level === "error" || e.level === "warning"));
      }
      const a = await fetch(API(p, "/api/setup/activity"));
      if (a.ok) {
        const y = await a.json();
        setToolEvents(y.events || []);
      }
      return x;
    } catch (e) {
      if (!quiet) setError(String(e));
      return null;
    }
  }

  async function pollDownload(p = port) {
    if (!p) return;
    try {
      const r = await fetch(API(p, "/api/setup/download"));
      if (r.ok) setDownload(await r.json());
    } catch {
      /* ignore */
    }
  }

  async function loadConfig(p = port) {
    if (!p) return;
    try {
      const r = await fetch(API(p, "/api/setup/config"));
      if (r.ok) {
        const x = await r.json();
        setConfig(x);
        setDraft(x.values || {});
      }
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      for (let attempt = 1; attempt <= 6; attempt++) {
        try {
          const p = await resolveSetupPort();
          if (!alive) return;
          setPort(p);
          setBootFailed(false);
          await refresh(p);
          await loadConfig(p);
          return;
        } catch (e) {
          if (attempt >= 6) {
            if (alive) {
              setBootFailed(true);
              setError("Could not start the Dana setup service: " + String(e));
              setMessage("Setup service unavailable");
            }
          } else {
            await new Promise((r) => setTimeout(r, 600 * attempt));
          }
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!port) return;
    let active = true;
    const t = window.setInterval(async () => {
      await refresh(port, true);
      if (!active) return;
      pollDownload(port);
    }, 2000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [port]);

  useEffect(() => {
    if (port && view === "Control") loadConfig(port);
  }, [port, view]);

  async function run(path: string, autoContinue = false) {
    if (!port || busy) return;
    setBusy(true);
    setError("");
    let completed = false;
    let pending = false;
    try {
      const r = await fetch(API(port, path), { method: "POST" });
      const x = await r.json();
      pending = !!x.pending;
      if (!r.ok || (x.ok === false && !x.pending))
        throw Error(x.message || x.error || "Action failed");
      completed = x.ok === true;
      setMessage(x.message || "Completed.");
      if (x.auth_url) {
        const kind = path.includes("login-tailscale") ? "login" : "funnel";
        setAuthFlow({
          pending: true,
          kind,
          auth_url: x.auth_url,
          message: x.message || "Complete the browser step.",
        });
        await openExternal(x.auth_url);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
      await refresh();
      pollDownload();
      if (autoContinue && completed && !pending) setTimeout(() => setup(), 150);
    }
  }

  useEffect(() => {
    if (!port || !authFlow?.pending) return;
    const t = window.setInterval(async () => {
      try {
        await refresh();
        const r = await fetch(API(port, "/api/setup/auth-flow"));
        if (!r.ok) return;
        const x = await r.json();
        if (!x.pending) {
          setAuthFlow(null);
          setTimeout(() => setup(), 150);
        }
      } catch {
        /* ignore */
      }
    }, 1000);
    return () => clearInterval(t);
  }, [port, authFlow?.pending]);

  async function setup() {
    if (!port) return;
    const current = await refresh(port);
    if (!current) return;
    if (!current.tailscale_installed) return run("/api/setup/install-tailscale", true);
    if (current.tailscale_backend.toLowerCase() !== "running")
      return run("/api/setup/login-tailscale", true);
    if (!current.dana_running) return run("/api/setup/start-dana", true);
    if (!current.funnel_active) {
      setAck(false);
      setConfirmPublic(true);
    }
  }

  async function dl(a: string) {
    if (!port) return;
    await fetch(API(port, "/api/setup/download/" + a), { method: "POST" });
    pollDownload();
  }

  async function copy(v: string) {
    if (!v) return;
    try {
      await navigator.clipboard.writeText(v);
      setCopied(v);
      setTimeout(() => setCopied(""), 1500);
    } catch {
      /* ignore */
    }
  }

  async function saveConfig() {
    if (!port) return;
    setSecurityBusy(true);
    try {
      const r = await fetch(API(port, "/api/setup/config"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: draft }),
      });
      const x = await r.json();
      if (!r.ok || x.ok === false) throw Error(x.message);
      setMessage(x.changed?.length ? "Updated: " + x.changed.join(", ") : "No changes.");
      await loadConfig();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSecurityBusy(false);
    }
  }

  async function applyToken() {
    if (!port || token.trim().length < 16) return;
    setSecurityBusy(true);
    try {
      const r = await fetch(API(port, "/api/setup/security/token"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const x = await r.json();
      if (!r.ok || x.ok === false) throw Error(x.message);
      setToken("");
      setMessage(x.message);
      await loadConfig();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSecurityBusy(false);
    }
  }

  async function revoke() {
    if (!port) return;
    setSecurityBusy(true);
    try {
      const r = await fetch(API(port, "/api/setup/security/revoke-token"), { method: "POST" });
      const x = await r.json();
      if (!r.ok || x.ok === false) throw Error(x.message);
      setToken("");
      setConfirmRevoke(false);
      setMessage(x.message);
      await loadConfig();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSecurityBusy(false);
    }
  }

  async function testConnection() {
    if (!port || testing) return;
    setTesting(true);
    setConnectionTest(null);
    try {
      const r = await fetch(API(port, "/api/setup/connection-test"));
      const x = await r.json();
      if (!r.ok) throw Error(x.message || "Connection test failed");
      setConnectionTest(x);
    } catch (e) {
      setError(String(e));
    } finally {
      setTesting(false);
    }
  }

  const dlVisible =
    !!download &&
    (download.active ||
      !!download.message &&
        (download.message.startsWith("Download cancelled") ||
          download.message.startsWith("Download failed") ||
          download.message.startsWith("Download complete") ||
          download.message.startsWith("Cancelling")));
  const dlPct = download?.total
    ? Math.min(100, (download.downloaded / download.total) * 100)
    : download?.active
      ? 30
      : 100;

  const navItems = ["Setup", "Control", "Logs"];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <img src={logo} alt="Dana" />
          </div>
          <div>
            <strong>DANA</strong>
            <span>Control Center</span>
          </div>
        </div>
        <nav>
          {navItems.map((x) => (
            <button
              key={x}
              className={view === x ? "nav-item active" : "nav-item"}
              onClick={() => setView(x)}
            >
              <span className="nav-dot" />
              {x}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="tiny-status">
            <span className={ready ? "pulse on" : "pulse"} />
            {ready ? "Online" : port ? "Setup required" : "Connecting…"}
          </div>
          <span>v{APP_VERSION}</span>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <div className="eyebrow">LOCAL CONTROL PLANE</div>
            <h1>{view}</h1>
          </div>
          <div className="top-actions">
            <div className="connection-pill">
              <span className={ready ? "dot on" : "dot"} />
              {ready
                ? "Protected endpoint active"
                : port
                  ? "Configuration in progress"
                  : "Starting service…"}
            </div>
            <button className="icon-button" onClick={() => refresh()} title="Refresh">
              ↻
            </button>
          </div>
        </header>

        {error && (
          <section className="alert-banner glass alert-error">
            <div className="alert-icon">!</div>
            <div className="alert-copy">
              <strong>Action error</strong>
              <p>{error}</p>
            </div>
            <button className="alert-close" onClick={() => setError("")}>
              ×
            </button>
          </section>
        )}

        {!port && !bootFailed && (
          <section className="boot-panel glass">
            <div className="boot-spinner" />
            <div>
              <strong>Starting setup service</strong>
              <p>{message}</p>
            </div>
          </section>
        )}

        {bootFailed && (
          <section className="boot-panel glass boot-failed">
            <div className="boot-fail-mark">!</div>
            <div>
              <strong>Setup service could not start</strong>
              <p>
                Ensure Python is available, then retry with <code>dana gui</code> or rebuild the
                desktop package.
              </p>
            </div>
          </section>
        )}

        {port && view === "Setup" && (
          <>
            <section className="hero glass">
              <div className="hero-copy">
                <span className="kicker">ONE-CLICK DEPLOYMENT</span>
                <h2>Bring Dana online without the terminal.</h2>
                <p>
                  Python runtime, Tailscale, Funnel and the public MCP endpoint are coordinated from
                  one setup flow.
                </p>
                <button
                  className="primary"
                  disabled={busy || ready || !status}
                  onClick={setup}
                >
                  {busy
                    ? "Working…"
                    : ready
                      ? "Dana is active"
                      : status?.tailscale_installed
                        ? "Activate Dana"
                        : "Install & Activate"}
                </button>
              </div>
              <div className="hero-side">
                <div className="hero-badge">
                  <img src={logo} alt="" />
                  <div>
                    <strong>Dana MCP</strong>
                    <span>Self-hosted agent runtime</span>
                  </div>
                </div>
              </div>
            </section>

            <div className="grid">
              {(
                [
                  [
                    "01",
                    "Tailscale",
                    status?.tailscale_installed,
                    "Install and authenticate Tailscale.",
                    status?.tailscale_backend || "Not connected",
                  ],
                  [
                    "02",
                    "Dana Runtime",
                    status?.dana_running,
                    "Start the local MCP service.",
                    localAddr,
                  ],
                  [
                    "03",
                    "Funnel",
                    status?.funnel_active,
                    "Publish the canonical HTTPS MCP endpoint.",
                    status?.funnel_hostname || "Not configured",
                  ],
                ] as const
              ).map(([n, name, ok, desc, meta]) => (
                <section className="card glass" key={String(name)}>
                  <div className="card-head">
                    <span>{n}</span>
                    <strong>{name}</strong>
                    <b className={ok ? "state success" : "state warning"}>
                      {ok ? "READY" : "PENDING"}
                    </b>
                  </div>
                  <p>{desc}</p>
                  <div className="meta">{meta}</div>
                </section>
              ))}
            </div>

            <section className="progress-card glass">
              <div className="progress-top">
                <div>
                  <span className="eyebrow">SETUP PROGRESS</span>
                  <strong>{progress}%</strong>
                </div>
                <span>{message || "Ready when you are."}</span>
              </div>
              <div className="track">
                <div className="track-fill" style={{ width: progress + "%" }} />
              </div>
              <div className="steps">
                <span className={status?.tailscale_installed ? "done" : ""}>Tailscale</span>
                <span
                  className={
                    status?.tailscale_backend?.toLowerCase() === "running" ? "done" : ""
                  }
                >
                  Authentication
                </span>
                <span className={status?.dana_running ? "done" : ""}>Dana</span>
                <span className={status?.funnel_active ? "done" : ""}>Funnel</span>
              </div>
            </section>
          </>
        )}

        {port && view === "Control" && (
          <div className="control-view">
            <div className="grid">
              <section className="card glass">
                <div className="card-head">
                  <span>RUNTIME</span>
                  <strong>Dana</strong>
                  <b className={status?.dana_running ? "state success" : "state warning"}>
                    {status?.dana_running ? "ONLINE" : "OFFLINE"}
                  </b>
                </div>
                <p>
                  {status?.dana_running
                    ? "MCP service is accepting connections."
                    : "Dana is not running."}
                </p>
                <div className="meta">{localAddr}</div>
                <div className="card-actions">
                  <button
                    className="primary"
                    disabled={busy || !!status?.dana_running}
                    onClick={() => run("/api/setup/start-dana")}
                  >
                    Start
                  </button>
                  <button
                    className="secondary"
                    disabled={busy || !status?.dana_running}
                    onClick={() => run("/api/setup/stop-dana")}
                  >
                    Stop
                  </button>
                </div>
              </section>
              <section className="card glass">
                <div className="card-head">
                  <span>NETWORK</span>
                  <strong>Tailscale</strong>
                  <b className="state success">{status?.tailscale_backend || "OFFLINE"}</b>
                </div>
                <p>{status?.tailscale_hostname || "Not connected"}</p>
                <div className="card-actions">
                  <button
                    className="secondary"
                    disabled={busy || !status?.tailscale_installed}
                    onClick={() => run("/api/setup/login-tailscale")}
                  >
                    Login
                  </button>
                  <button
                    className="secondary"
                    disabled={busy || !status?.dana_running}
                    onClick={() => {
                      setAck(false);
                      setConfirmPublic(true);
                    }}
                  >
                    Enable Funnel
                  </button>
                </div>
              </section>
              <section className="card glass">
                <div className="card-head">
                  <span>PUBLIC</span>
                  <strong>Funnel</strong>
                  <b className={status?.funnel_active ? "state success" : "state warning"}>
                    {status?.funnel_active ? "ACTIVE" : "INACTIVE"}
                  </b>
                </div>
                <p>{status?.funnel_hostname || "Not configured"}</p>
                <div className="meta">{status?.funnel_active ? "HTTPS :443 → local MCP" : "—"}</div>
              </section>
            </div>

            <section className="connections-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">MCP CONNECTIONS</span>
                  <h2>Endpoints</h2>
                </div>
                <button className="secondary" onClick={testConnection} disabled={testing}>
                  {testing ? "Testing…" : "Test connection"}
                </button>
              </div>
              <div className="connection-list">
                {(
                  [
                    ["LOCAL", status?.local_mcp_url],
                    ["FUNNEL", status?.public_mcp_url],
                  ] as const
                ).map(([label, url]) => (
                  <div className="connection-row" key={label}>
                    <div>
                      <span className="eyebrow">{label}</span>
                      <strong>
                        {label === "LOCAL" ? "Local MCP endpoint" : "Public MCP endpoint"}
                      </strong>
                      <code>{url || "Unavailable"}</code>
                    </div>
                    <button className="secondary" disabled={!url} onClick={() => copy(url || "")}>
                      {copied === url ? "Copied" : "Copy"}
                    </button>
                  </div>
                ))}
              </div>
              {connectionTest && (
                <div
                  className={
                    connectionTest.ok ? "connection-test success" : "connection-test error"
                  }
                >
                  {connectionTest.checks.map((c) => (
                    <span key={c.name}>
                      {c.name.toUpperCase()}:{" "}
                      {c.ok ? "OK" : c.error || "HTTP " + (c.status || "error")}
                    </span>
                  ))}
                </div>
              )}
            </section>

            <section className="connections-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">AUTHENTICATION</span>
                  <h2>Token</h2>
                </div>
                <b className={config?.auth_token_configured ? "state success" : "state warning"}>
                  {config?.auth_token_configured ? "READY" : "MISSING"}
                </b>
              </div>
              <div className="security-token">
                <span className="eyebrow">CURRENT TOKEN</span>
                <code>{config?.auth_token || "Not configured"}</code>
              </div>
              <div className="token-editor">
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Custom token, 16–256 characters"
                />
                <button
                  className="primary"
                  disabled={securityBusy || token.length < 16}
                  onClick={applyToken}
                >
                  Apply
                </button>
              </div>
              <div className="modal-actions">
                {!confirmRevoke ? (
                  <button
                    className="secondary danger-button"
                    disabled={securityBusy}
                    onClick={() => setConfirmRevoke(true)}
                  >
                    Revoke & replace
                  </button>
                ) : (
                  <>
                    <span className="logs-description">Existing URLs will stop working.</span>
                    <button
                      className="secondary"
                      disabled={securityBusy}
                      onClick={() => setConfirmRevoke(false)}
                    >
                      Cancel
                    </button>
                    <button
                      className="secondary danger-button"
                      disabled={securityBusy}
                      onClick={revoke}
                    >
                      Confirm
                    </button>
                  </>
                )}
              </div>
            </section>

            <section className="connections-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">ENVIRONMENT</span>
                  <h2>Configuration</h2>
                </div>
                <button className="primary" disabled={securityBusy} onClick={saveConfig}>
                  Save
                </button>
              </div>
              <div className="config-grid">
                {config?.keys
                  .filter((k) => k !== "DANA_AUTH_TOKEN")
                  .map((k) => (
                    <label className="config-field" key={k}>
                      <span>{k}</span>
                      {k === "DANA_ALLOW_DANGEROUS_TOOLS" ||
                      k === "DANA_TAILSCALE_FUNNEL_ENABLED" ? (
                        <select
                          value={draft[k] ?? config.defaults?.[k] ?? "false"}
                          onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                        >
                          <option value="true">true</option>
                          <option value="false">false</option>
                        </select>
                      ) : k === "DANA_ALLOWED_PATHS" || k === "DANA_DENIED_PATHS" ? (
                        <textarea
                          value={draft[k] ?? ""}
                          placeholder="One path per line"
                          onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                        />
                      ) : (
                        <input
                          value={draft[k] ?? config.defaults?.[k] ?? ""}
                          onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                        />
                      )}
                    </label>
                  ))}
              </div>
            </section>
          </div>
        )}

        {port && view === "Logs" && (
          <div className="logs-split">
            <section className="logs-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">SYSTEM · ERRORS</span>
                  <h2>Setup & errors</h2>
                </div>
                <div className="log-head-actions">
                  {!!errorLogs.length && (
                    <span className="error-badge">{errorLogs.length} warnings/errors</span>
                  )}
                  <button className="secondary" onClick={() => refresh()}>
                    Refresh
                  </button>
                </div>
              </div>
              <p className="logs-description">
                Install, download, authentication, Funnel, warnings and failures.
              </p>
              <div className="log-list">
                {logs.length ? (
                  logs
                    .slice()
                    .reverse()
                    .map((x, i) => (
                      <div className={"log-row log-" + x.level} key={x.time + x.message + i}>
                        <span className="log-time">{x.time}</span>
                        <span className={"log-level " + x.level}>{x.level.toUpperCase()}</span>
                        <span className="log-message">{x.message}</span>
                      </div>
                    ))
                ) : (
                  <div className="log-empty">No setup events yet.</div>
                )}
              </div>
            </section>

            <section className="logs-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">TOOL ACTIVITY</span>
                  <h2>Dana tools</h2>
                </div>
                <button className="secondary" onClick={() => refresh()}>
                  Refresh
                </button>
              </div>
              <p className="logs-description">
                Live tool usage from MCP clients — the same activity stream shown in the terminal.
              </p>
              <div className="log-list tool-log-list">
                {toolEvents.length ? (
                  toolEvents.map((ev, i) => (
                    <div
                      className={"log-row tool-row " + (ev.success ? "log-success" : "log-error")}
                      key={ev.time + ev.tool + i}
                    >
                      <span className="log-time">{ev.time}</span>
                      <span className={ev.success ? "log-level success" : "log-level error"}>
                        {ev.success ? "OK" : "FAIL"}
                      </span>
                      <span className="log-message">
                        <code>{ev.tool}</code>
                        {" · "}
                        {ev.worker}
                        {ev.number ? " #" + ev.number : ""}
                        {" · "}
                        {Math.round(ev.duration_ms)} ms
                        {" · "}
                        {(ev.input + ev.output).toLocaleString()} tok
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="log-empty">
                    No tool activity yet. Connect an MCP client and run tools to see them here.
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
        </main>

      {authFlow?.pending && (
        <div className="modal-backdrop">
          <div className="modal glass auth-modal">
            <div className="modal-icon">↗</div>
            <div className="eyebrow">BROWSER ACTION REQUIRED</div>
            <h2>
              {authFlow.kind === "login"
                ? "Sign in to Tailscale"
                : "Approve Tailscale Funnel"}
            </h2>
            <p>{authFlow.message}</p>
            <p className="auth-instruction">
              Copy this link and open it in your browser to complete the step.
              Keep this window open — Dana continues automatically after you finish.
            </p>
            <div className="security-token">
              <span className="eyebrow">
                {authFlow.kind === "login" ? "TAILSCALE LOGIN URL" : "FUNNEL APPROVAL URL"}
              </span>
              <code>{authFlow.auth_url}</code>
            </div>
            <div className="modal-actions auth-actions">
              <button className="secondary" onClick={() => copy(authFlow.auth_url)}>
                {copied === authFlow.auth_url ? "Copied" : "Copy link"}
              </button>
              <button className="primary" onClick={() => openExternal(authFlow.auth_url)}>
                Open in browser
              </button>
            </div>
            <p className="logs-description">
              If the browser does not open automatically, paste the copied link into Chrome,
              Firefox, or Edge and finish authentication or Funnel approval there.
            </p>
          </div>
        </div>
      )}

      {confirmPublic && (
        <div className="modal-backdrop">
          <div className="modal glass">
            <div className="modal-icon">!</div>
            <div className="eyebrow">PUBLIC INTERNET EXPOSURE</div>
            <h2>Enable Tailscale Funnel?</h2>
            <p>This publishes Dana’s HTTPS endpoint to the public internet.</p>
            <label className="confirm-line">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
              <span>I understand that Funnel makes the endpoint publicly reachable.</span>
            </label>
            <div className="modal-actions">
              <button className="secondary" onClick={() => setConfirmPublic(false)}>
                Cancel
              </button>
              <button
                className="primary"
                disabled={!ack || busy}
                onClick={() => {
                  setConfirmPublic(false);
                  run("/api/setup/enable-funnel");
                }}
              >
                Enable Funnel
              </button>
            </div>
          </div>
        </div>
      )}

      {dlVisible && download && (
        <div className="modal-backdrop">
          <div className="download-modal glass">
            <div className="download-header">
              <div>
                <span className="eyebrow">DOWNLOAD</span>
                <h2>{download.name || "Downloading"}</h2>
              </div>
              <b
                className={
                  download.active
                    ? download.paused
                      ? "state warning"
                      : "state success"
                    : download.message.startsWith("Download failed")
                      ? "state error"
                      : download.message.startsWith("Download cancelled")
                        ? "state warning"
                        : "state success"
                }
              >
                {download.active
                  ? download.paused
                    ? "PAUSED"
                    : "IN PROGRESS"
                  : download.message.startsWith("Download failed")
                    ? "FAILED"
                    : download.message.startsWith("Download cancelled")
                      ? "CANCELLED"
                      : "FINISHED"}
              </b>
            </div>
            <p className="logs-description">{download.message}</p>
            {(download.attempt || download.source) && (
              <div className="download-source">
                <span className="eyebrow">SOURCE</span>
                <code>
                  {download.attempt && download.attempts_total
                    ? `${download.attempt}/${download.attempts_total} · `
                    : ""}
                  {download.source || "—"}
                </code>
              </div>
            )}
            <div className="download-progress">
              <div className="download-fill" style={{ width: dlPct + "%" }} />
            </div>
            <div className="download-stats">
              <span>
                {download.total
                  ? dlPct.toFixed(1) + "%"
                  : download.active
                    ? "Receiving…"
                    : "—"}
              </span>
              <span>
                {bytes(download.downloaded)} / {bytes(download.total)}
              </span>
              <span>{speed(download.speed)}</span>
            </div>
            {!!download.errors?.length && (
              <div className="download-errors">
                <span className="eyebrow">FAILED SOURCES (LOGGED)</span>
                <ul>
                  {download.errors.slice(-4).map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="modal-actions">
              {download.active ? (
                <>
                  <button
                    className="secondary"
                    onClick={() => dl(download.paused ? "resume" : "pause")}
                  >
                    {download.paused ? "Resume" : "Pause"}
                  </button>
                  <button className="secondary danger-button" onClick={() => dl("cancel")}>
                    Cancel download
                  </button>
                </>
              ) : (
                <button
                  className="secondary"
                  onClick={() => setDownload(null)}
                >
                  Close
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
