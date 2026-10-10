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
type UsageState = {
  available: boolean;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  operations: number;
  active_seconds?: number;
  session_seconds?: number;
  exact_tokens?: number;
  estimated_tokens?: number;
  success_rate?: number;
  started_at?: string;
  last_at?: string;
  top_tools?: { name: string; count: number }[];
  recent_events?: {
    time: string;
    tool: string;
    worker: string;
    input: number;
    output: number;
    duration_ms: number;
    success: boolean;
    source: string;
  }[];
  report_json?: string;
  report_html?: string;
};
type UpdateInfo = {
  ok: boolean;
  current?: string;
  latest?: string;
  available?: boolean;
  html_url?: string;
  message?: string;
  assets?: { name: string; url: string }[];
};
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

const fmtDuration = (seconds: number) => {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h) return `${h}h ${m}m ${r}s`;
  if (m) return `${m}m ${r}s`;
  return `${r}s`;
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
  if (!url) return;
  try {
    await openUrl(url);
    return;
  } catch {
    /* fall through */
  }
  try {
    const opened = window.open(url, "_blank", "noopener,noreferrer");
    if (opened) return;
  } catch {
    /* fall through */
  }
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    /* ignore */
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
  const [pendingInstall, setPendingInstall] = useState(false);
  const [manualUrl, setManualUrl] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try {
      const saved = localStorage.getItem("dana-theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch { /* ignore */ }
    return "dark";
  });
  const [accent, setAccent] = useState<"blue" | "green" | "red">(() => {
    try {
      const saved = localStorage.getItem("dana-accent");
      if (saved === "blue" || saved === "green" || saved === "red") return saved;
    } catch { /* ignore */ }
    return "blue";
  });
  const [usage, setUsage] = useState<UsageState | null>(null);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);

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
      const u = await fetch(API(p, "/api/setup/usage"));
      if (u.ok) {
        const y = await u.json();
        setUsage(y);
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

  useEffect(() => {
    try {
      localStorage.setItem("dana-theme", theme);
      localStorage.setItem("dana-accent", accent);
    } catch { /* ignore */ }
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-accent", accent);
  }, [theme, accent]);

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
      if (x.action_required === "finish_installer") setPendingInstall(true);
      if (typeof x.url === "string" && x.url) setManualUrl(x.url);
      if (!r.ok || (x.ok === false && !x.pending))
        throw Error(x.message || x.error || "Action failed");
      completed = x.ok === true;
      setMessage(x.message || "Completed.");
      setUpdateInfo(null);
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
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg.replace(/^Error:\s*/i, ""));
      setUpdateInfo(null);
    } finally {
      setBusy(false);
      await refresh();
      pollDownload();
      if (completed && !pending) setPendingInstall(false);
      // After installer actions, give PATH/status a moment to settle then continue.
      if (autoContinue && completed && !pending) setTimeout(() => setup(), 400);
      if (autoContinue && completed && pending && path.includes("install-tailscale")) {
        // Windows/macOS open an external installer — keep polling for CLI presence.
        setPendingInstall(true);
      }
    }
  }

  // After external Tailscale installer finishes, detect CLI and continue setup
  // without requiring the user to restart the whole application.
  useEffect(() => {
    if (!port || !pendingInstall) return;
    const t = window.setInterval(async () => {
      const current = await refresh(port, true);
      if (!current) return;
      if (current.tailscale_installed) {
        setPendingInstall(false);
        setMessage("Tailscale detected. Continuing setup…");
        setTimeout(() => setup(), 200);
      }
    }, 2000);
    return () => clearInterval(t);
  }, [port, pendingInstall]);

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

  const downloadFinished =
    !!download &&
    !download.active &&
    !!download.message &&
    download.message.startsWith("Download complete");
  const dlVisible =
    !!download &&
    (download.active ||
      (!!download.message &&
        (download.message.startsWith("Download cancelled") ||
          download.message.startsWith("Download failed") ||
          download.message.startsWith("Cancelling"))));
  const dlPct = download?.total
    ? Math.min(100, (download.downloaded / download.total) * 100)
    : download?.active
      ? 30
      : 100;

  // When a download finishes successfully, hide the modal and continue setup
  // without requiring a manual Continue click (avoids the 100% stuck dialog).
  useEffect(() => {
    if (!port || !downloadFinished) return;
    const t = window.setTimeout(() => {
      setDownload(null);
      setMessage("Download finished. Continuing setup…");
      setup();
    }, 600);
    return () => clearTimeout(t);
  }, [port, downloadFinished]);

  async function checkUpdates() {
    if (!port || updateBusy) return;
    setUpdateBusy(true);
    try {
      const r = await fetch(API(port, "/api/setup/updates/check"));
      const x = await r.json();
      setUpdateInfo(x);
      if (x.message) setMessage(x.message);
    } catch (e) {
      setError(String(e));
    } finally {
      setUpdateBusy(false);
    }
  }

  const navItems: { id: "Setup" | "Control" | "Usage" | "Logs"; label: string; icon: string }[] = [
    { id: "Setup", label: "Setup", icon: "setup" },
    { id: "Control", label: "Control", icon: "control" },
    { id: "Usage", label: "Usage", icon: "usage" },
    { id: "Logs", label: "Logs", icon: "logs" },
  ];

  function NavIcon({ name }: { name: string }) {
    if (name === "setup")
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.7" />
        </svg>
      );
    if (name === "control")
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="1.7" />
          <path d="M7 9h4M7 13h10M7 17h7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      );
    if (name === "usage")
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 19V5M4 19h16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          <path d="M8 15v-4M12 15V8M16 15v-6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      );
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M5 6h14M5 12h14M5 18h10" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <div className={`shell theme-${theme} accent-${accent}`} data-theme={theme} data-accent={accent}>
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
              key={x.id}
              className={view === x.id ? "nav-item active" : "nav-item"}
              onClick={() => setView(x.id)}
            >
              <span className="nav-icon">
                <NavIcon name={x.icon} />
              </span>
              {x.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="tiny-status">
            <span className={ready ? "pulse on" : "pulse"} />
            {ready ? "Online" : port ? "Setup required" : "Connecting…"}
          </div>
          <div className="sidebar-version-row">
            <span className="version-badge">v{APP_VERSION}</span>
            <button
              type="button"
              className="update-check-btn"
              onClick={() => checkUpdates()}
              disabled={updateBusy || !port}
            >
              {updateBusy ? "Checking…" : "Check for updates"}
            </button>
          </div>
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
                      <div className="theme-controls" role="group" aria-label="Theme">
              <label className="accent-select-wrap" title="Accent color">
                <span className={`accent-dot ${accent}`} aria-hidden="true" />
                <select
                  className="accent-select"
                  value={accent}
                  onChange={(e) => setAccent(e.target.value as "blue" | "green" | "red")}
                  aria-label="Accent color"
                >
                  <option value="blue">Blue</option>
                  <option value="green">Green</option>
                  <option value="red">Red</option>
                </select>
              </label>
              <button
                type="button"
                className="icon-button theme-toggle"
                onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
                title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              >
                {theme === "dark" ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M21 14.3A8.5 8.5 0 0 1 9.7 3 7 7 0 1 0 21 14.3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M12 2v2.2M12 19.8V22M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2 12h2.2M19.8 12H22M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                )}
              </button>
              <button type="button" className="icon-button" onClick={() => refresh()} title="Refresh" aria-label="Refresh">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </header>

        <div className="notice-stack">
        {updateInfo && (
          <section
            className={
              updateInfo.available ? "notice-card notice-info" : "notice-card notice-success"
            }
          >
            <div className="notice-body">
              <span className="notice-badge">{updateInfo.available ? "UPDATE" : "OK"}</span>
              <div>
                <strong>{updateInfo.message || "Update check"}</strong>
                {updateInfo.available && updateInfo.html_url && (
                  <div className="card-actions" style={{ marginTop: 8 }}>
                    <button className="primary" onClick={() => openExternal(updateInfo.html_url || "")}>
                      Open release v{updateInfo.latest}
                    </button>
                    {(updateInfo.assets || []).slice(0, 3).map((a) => (
                      <button key={a.url} className="secondary" onClick={() => openExternal(a.url)}>
                        {a.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <button type="button" className="notice-close" onClick={() => setUpdateInfo(null)} aria-label="Dismiss">
              ×
            </button>
          </section>
        )}

        {error && (
          <section className="notice-card notice-error">
            <div className="notice-body">
              <span className="notice-badge">ERROR</span>
              <div>
                <strong>Action failed</strong>
                <p>{error}</p>
              </div>
            </div>
            <button type="button" className="notice-close" onClick={() => setError("")} aria-label="Dismiss">
              ×
            </button>
          </section>
        )}

        {!error && !!message && !!port && !message.startsWith("Starting") && (
          <section className="notice-card notice-muted">
            <div className="notice-body">
              <span className="notice-badge">INFO</span>
              <div>
                <strong>{message}</strong>
              </div>
            </div>
            <button type="button" className="notice-close" onClick={() => setMessage("")} aria-label="Dismiss">
              ×
            </button>
          </section>
        )}
      </div>

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
                {pendingInstall && (
                  <div className="pending-banner">
                    <p>
                      Finish the Tailscale installer window, then continue here.
                      The OS may ask for an administrator password (UAC / sudo / macOS prompt).
                    </p>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => {
                        setPendingInstall(false);
                        setup();
                      }}
                    >
                      Continue after install
                    </button>
                  </div>
                )}
                {!!manualUrl && !!error && (
                  <div className="pending-banner">
                    <p>
                      Automatic download failed. Open the official Tailscale page, install
                      manually, then continue.
                    </p>
                    <div className="modal-actions">
                      <button className="secondary" onClick={() => openExternal(manualUrl)}>
                        Open Tailscale download
                      </button>
                      <button className="primary" disabled={busy} onClick={() => setup()}>
                        Retry / Continue
                      </button>
                    </div>
                  </div>
                )}
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
              <button
                className="secondary"
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
              >
                {showAdvanced ? "Hide advanced settings" : "Show advanced settings"}
              </button>
              {showAdvanced && (
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
              )}
            </section>
          </div>
        )}

        {port && view === "Usage" && (
        <div className="usage-view">
          <section className="card glass usage-hero">
            <div className="card-head">
              <span>USAGE</span>
              <strong>Lifetime report</strong>
              <b className={usage?.available ? "state success" : "state warning"}>
                {usage?.available ? "LIVE" : "WAITING"}
              </b>
            </div>
            <p className="logs-description">
              Cumulative totals stored locally (same data as the terminal report). Started{" "}
              {usage?.started_at || "—"} · Last activity {usage?.last_at || "—"}.
            </p>
          </section>
          <div className="grid usage-grid">
            <section className="card glass">
              <span className="eyebrow">TOTAL TOKENS</span>
              <div className="usage-value">{(usage?.total_tokens ?? 0).toLocaleString()}</div>
            </section>
            <section className="card glass">
              <span className="eyebrow">INPUT</span>
              <div className="usage-value">{(usage?.input_tokens ?? 0).toLocaleString()}</div>
            </section>
            <section className="card glass">
              <span className="eyebrow">OUTPUT</span>
              <div className="usage-value">{(usage?.output_tokens ?? 0).toLocaleString()}</div>
            </section>
            <section className="card glass">
              <span className="eyebrow">OPERATIONS</span>
              <div className="usage-value">{(usage?.operations ?? 0).toLocaleString()}</div>
            </section>
            <section className="card glass">
              <span className="eyebrow">SUCCESS RATE</span>
              <div className="usage-value">{(usage?.success_rate ?? 100).toFixed(1)}%</div>
            </section>
            <section className="card glass">
              <span className="eyebrow">ACTIVE TOOL TIME</span>
              <div className="usage-value">{fmtDuration(usage?.active_seconds ?? 0)}</div>
            </section>
          </div>
          <div className="grid two">
            <section className="connections-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">TOP TOOLS</span>
                  <h2>Most used</h2>
                </div>
                <button className="secondary" onClick={() => refresh()}>
                  Refresh
                </button>
              </div>
              <div className="usage-tool-list">
                {(usage?.top_tools || []).length ? (
                  (usage?.top_tools || []).map((t) => (
                    <div className="usage-tool-row" key={t.name}>
                      <code>{t.name}</code>
                      <strong>{t.count.toLocaleString()}</strong>
                    </div>
                  ))
                ) : (
                  <div className="log-empty">No tool activity yet.</div>
                )}
              </div>
            </section>
            <section className="connections-panel glass">
              <div className="logs-head">
                <div>
                  <span className="eyebrow">BREAKDOWN</span>
                  <h2>Token source</h2>
                </div>
              </div>
              <div className="usage-breakdown">
                <div>
                  <span className="eyebrow">EXACT</span>
                  <strong>{(usage?.exact_tokens ?? 0).toLocaleString()}</strong>
                </div>
                <div>
                  <span className="eyebrow">ESTIMATED</span>
                  <strong>{(usage?.estimated_tokens ?? 0).toLocaleString()}</strong>
                </div>
              </div>
              <p className="logs-description" style={{ marginTop: 12 }}>
                Report file: <code>{usage?.report_json || "—"}</code>
              </p>
            </section>
          </div>
          <section className="connections-panel glass">
            <div className="logs-head">
              <div>
                <span className="eyebrow">RECENT OPERATIONS</span>
                <h2>Activity</h2>
              </div>
            </div>
            <div className="log-list tool-log-list">
              {(usage?.recent_events || []).length ? (
                (usage?.recent_events || []).map((e, i) => (
                  <div
                    className={"log-row log-" + (e.success ? "success" : "error")}
                    key={e.time + e.tool + i}
                  >
                    <span className="log-time">{e.time}</span>
                    <span className={"log-level " + (e.success ? "success" : "error")}>
                      {e.success ? "OK" : "FAIL"}
                    </span>
                    <span className="log-message">
                      {e.tool} · {e.input + e.output} tok · {Math.round(e.duration_ms)}ms
                    </span>
                  </div>
                ))
              ) : (
                <div className="log-empty">No operations recorded yet.</div>
              )}
            </div>
          </section>
        </div>
      )}

      {port && view === "Logs" && (
          <div className="logs-stack">
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
                <>
                  {download.message.startsWith("Download failed") && !!manualUrl && (
                    <button className="secondary" onClick={() => openExternal(manualUrl)}>
                      Open manual download
                    </button>
                  )}
                  <button
                    className="primary"
                    onClick={() => {
                      setDownload(null);
                      if (!download.message.startsWith("Download failed")) setup();
                    }}
                  >
                    {download.message.startsWith("Download failed") ? "Close" : "Continue"}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
