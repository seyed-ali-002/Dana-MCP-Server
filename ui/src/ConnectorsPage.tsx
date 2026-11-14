import { useEffect, useState } from "react";

const API = (p: number, path: string) => "http://127.0.0.1:" + p + path;

type ConnectorRow = {
  name: string;
  kind: string;
  enabled: boolean;
  command?: string;
  args?: string[];
  url?: string;
  description?: string;
};

type ToolRow = { name: string; category?: string; description?: string };

type Props = {
  port: number;
  setMessage: (m: string) => void;
  setError: (e: string) => void;
};

export default function ConnectorsPage({ port, setMessage, setError }: Props) {
  const [connectorList, setConnectorList] = useState<ConnectorRow[]>([]);
  const [toolCatalog, setToolCatalog] = useState<ToolRow[]>([]);
  const [connectorBusy, setConnectorBusy] = useState(false);
  const [connName, setConnName] = useState("");
  const [connCommand, setConnCommand] = useState("npx");
  const [connArgs, setConnArgs] = useState("");
  const [connEnv, setConnEnv] = useState("");
  const [connUrl, setConnUrl] = useState("");
  const [connJson, setConnJson] = useState(`{\n  "mcpServers": {\n    "godot": {\n      "command": "npx",\n      "args": ["@coding-solo/godot-mcp"],\n      "env": { "GODOT_PATH": "/path/to/Godot" }\n    }\n  }\n}`);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [cRes, tRes] = await Promise.all([
          fetch(API(port, "/api/setup/connectors"), { cache: "no-store" }),
          fetch(API(port, "/api/setup/tools/catalog"), { cache: "no-store" }),
        ]);
        if (cancelled) return;
        if (cRes.ok) {
          const j = await cRes.json();
          setConnectorList(j.connectors || []);
        }
        if (tRes.ok) {
          const j = await tRes.json();
          setToolCatalog(j.tools || []);
        }
      } catch {
        /* ignore */
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [port]);

  return (
    <section className="connectors-page skills-page">
      <header className="skills-page-head">
        <div>
          <span className="eyebrow">SUPERMCP · MCP SERVERS</span>
          <h2>Connectors &amp; Tools</h2>
          <p className="muted">
            ابزارهای داخلی دانا همیشه در Super MCP ثبت‌اند. اینجا می‌توانید MCP Serverهای اضافه
            (مثل Godot) را با فرمت <code>mcpServers</code> اضافه یا import کنید.
          </p>
        </div>
        <div className="row gap">
          <button
            className="secondary"
            disabled={connectorBusy || !port}
            onClick={async () => {
              if (!port) return;
              setConnectorBusy(true);
              try {
                const r = await fetch(API(port, "/api/setup/supermcp/refresh"), { method: "POST" });
                const j = await r.json();
                setMessage(j.message || "SuperMCP refreshed");
                const c = await fetch(API(port, "/api/setup/connectors"), { cache: "no-store" });
                if (c.ok) setConnectorList((await c.json()).connectors || []);
                const t = await fetch(API(port, "/api/setup/tools/catalog"), { cache: "no-store" });
                if (t.ok) setToolCatalog((await t.json()).tools || []);
              } catch (e) {
                setError(String(e));
              } finally {
                setConnectorBusy(false);
              }
            }}
          >
            Refresh SuperMCP
          </button>
        </div>
      </header>

      <div className="glass panel" style={{ marginBottom: 16 }}>
        <h3>Dana tools (built-in)</h3>
        <p className="muted tiny">همهٔ این ابزارها از طریق upstream سرور Dana در SuperMCP در دسترس‌اند.</p>
        <div className="fl-group-list" style={{ maxHeight: 220, overflow: "auto" }}>
          {toolCatalog.length === 0 ? (
            <p className="muted">No catalog yet — start Dana then click Refresh SuperMCP.</p>
          ) : (
            toolCatalog.slice(0, 80).map((t) => (
              <div key={t.name} className="fl-group-item">
                <strong>{t.name}</strong>
                <span className="muted tiny">{t.category || "general"}</span>
                <span className="muted tiny">{t.description || ""}</span>
              </div>
            ))
          )}
        </div>
        {toolCatalog.length > 80 && <p className="muted tiny">Showing 80 of {toolCatalog.length}</p>}
      </div>

      <div className="glass panel" style={{ marginBottom: 16 }}>
        <h3>Extra connectors</h3>
        {connectorList.length === 0 ? (
          <p className="muted">هنوز کانکتور اضافه‌ای ثبت نشده.</p>
        ) : (
          <table className="connectors-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Kind</th>
                <th>Command / URL</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {connectorList.map((c) => (
                <tr key={c.name}>
                  <td>
                    <strong>{c.name}</strong>
                  </td>
                  <td>{c.kind}</td>
                  <td className="mono tiny">
                    {c.command ? `${c.command} ${(c.args || []).join(" ")}` : c.url || ""}
                  </td>
                  <td>
                    <button
                      className="danger tiny-btn"
                      disabled={connectorBusy}
                      onClick={async () => {
                        if (!port) return;
                        setConnectorBusy(true);
                        try {
                          await fetch(API(port, "/api/setup/connectors/remove"), {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name: c.name }),
                          });
                          const res = await fetch(API(port, "/api/setup/connectors"), { cache: "no-store" });
                          if (res.ok) setConnectorList((await res.json()).connectors || []);
                          setMessage(`Removed ${c.name}`);
                        } finally {
                          setConnectorBusy(false);
                        }
                      }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="glass panel" style={{ marginBottom: 16 }}>
        <h3>Add connector (stdio / HTTP)</h3>
        <div className="form-grid">
          <label>
            Name
            <input value={connName} onChange={(e) => setConnName(e.target.value)} placeholder="godot" />
          </label>
          <label>
            Command (stdio)
            <input value={connCommand} onChange={(e) => setConnCommand(e.target.value)} placeholder="npx" />
          </label>
          <label>
            Args (space-separated)
            <input value={connArgs} onChange={(e) => setConnArgs(e.target.value)} placeholder="@coding-solo/godot-mcp" />
          </label>
          <label>
            Env KEY=VALUE (one per line)
            <textarea rows={3} value={connEnv} onChange={(e) => setConnEnv(e.target.value)} placeholder="GODOT_PATH=/path/to/Godot" />
          </label>
          <label>
            Or URL (HTTP / SSE)
            <input value={connUrl} onChange={(e) => setConnUrl(e.target.value)} placeholder="http://127.0.0.1:9000/mcp" />
          </label>
        </div>
        <button
          className="primary"
          disabled={connectorBusy || !connName.trim() || (!connCommand.trim() && !connUrl.trim())}
          onClick={async () => {
            if (!port) return;
            setConnectorBusy(true);
            try {
              const env: Record<string, string> = {};
              for (const line of connEnv.split("\n")) {
                const t = line.trim();
                if (!t || !t.includes("=")) continue;
                const i = t.indexOf("=");
                env[t.slice(0, i).trim()] = t.slice(i + 1).trim();
              }
              const config: Record<string, unknown> = { enabled: true };
              if (connUrl.trim()) config.url = connUrl.trim();
              if (connCommand.trim()) {
                config.command = connCommand.trim();
                config.args = connArgs.trim() ? connArgs.trim().split(/\s+/) : [];
              }
              if (Object.keys(env).length) config.env = env;
              const r = await fetch(API(port, "/api/setup/connectors/upsert"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: connName.trim(), config }),
              });
              const j = await r.json();
              setMessage(j.message || "Saved");
              const res = await fetch(API(port, "/api/setup/connectors"), { cache: "no-store" });
              if (res.ok) setConnectorList((await res.json()).connectors || []);
            } catch (e) {
              setError(String(e));
            } finally {
              setConnectorBusy(false);
            }
          }}
        >
          Save connector
        </button>
      </div>

      <div className="glass panel" style={{ marginBottom: 16 }}>
        <h3>Import JSON (mcpServers)</h3>
        <textarea
          className="code-block"
          rows={10}
          value={connJson}
          onChange={(e) => setConnJson(e.target.value)}
          spellCheck={false}
        />
        <button
          className="secondary"
          disabled={connectorBusy}
          onClick={async () => {
            if (!port) return;
            setConnectorBusy(true);
            try {
              const payload = JSON.parse(connJson);
              const r = await fetch(API(port, "/api/setup/connectors/import"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
              });
              const j = await r.json();
              setMessage(j.message || "Imported");
              const res = await fetch(API(port, "/api/setup/connectors"), { cache: "no-store" });
              if (res.ok) setConnectorList((await res.json()).connectors || []);
            } catch (e) {
              setError(String(e));
            } finally {
              setConnectorBusy(false);
            }
          }}
        >
          Import JSON
        </button>
      </div>

      <div className="glass panel guide-block">
        <h3>Guide · راهنما</h3>
        <ul className="guide-list">
          <li>
            Super MCP Assistant SSE: <code>http://127.0.0.1:3006/sse</code>
          </li>
          <li>
            نام <code>Dana</code> رزرو شده است و overwrite نمی‌شود.
          </li>
          <li>
            بعد از افزودن/حذف، <strong>Refresh SuperMCP</strong> را بزنید تا پروکسی کانفیگ جدید را بخواند.
          </li>
          <li>
            مثال Godot با <code>command</code> + <code>args</code> + <code>env.GODOT_PATH</code> در باکس Import آماده است.
          </li>
          <li>
            Config path: <code>~/.config/dana/supermcp/config.json</code> · Connectors:{" "}
            <code>~/.config/dana/connectors/user_connectors.json</code>
          </li>
        </ul>
      </div>
    </section>
  );
}
