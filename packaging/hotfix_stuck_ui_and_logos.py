#!/usr/bin/env python3
"""Fix stuck Configuration-in-progress UI + regenerate icons from dana-logo."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_setup() -> None:
    path = ROOT / "dana" / "setup.py"
    t = path.read_text(encoding="utf-8")
    if "_PUBLIC_VERIFY_CACHE" not in t:
        t = t.replace(
            '_CONNECTION_MODE = "all"',
            '_CONNECTION_MODE = "all"\n_PUBLIC_VERIFY_CACHE: dict[str, object] = {"host": "", "ok": False, "ts": 0.0}\n_PUBLIC_VERIFY_TTL = 30.0',
            1,
        )
    old = '''    else:
        # Light public check — failures mean degraded, not offline.
        try:
            public_verified = False
            if funnel_host:
                for _attempt in range(3):
                    public_verified = verify_public_endpoint(funnel_host, timeout=4.0)
                    if public_verified:
                        break
                    time.sleep(0.6 * (_attempt + 1))
        except Exception:
            public_verified = False
        if public_verified:
            connectivity = "connected"
            hint = "Local and public MCP endpoints look healthy."
        else:
            connectivity = "degraded"
            hint = (
                "Funnel is published but the public URL is not responding yet. "
                "Wait a few seconds or click Repair connection."
            )'''
    new = '''    else:
        # Fast public check with short TTL cache so /status never blocks the UI.
        public_verified = False
        try:
            if funnel_host:
                now = time.monotonic()
                cache_host = str(_PUBLIC_VERIFY_CACHE.get("host") or "")
                cache_ts = float(_PUBLIC_VERIFY_CACHE.get("ts") or 0.0)
                if cache_host == funnel_host and (now - cache_ts) < _PUBLIC_VERIFY_TTL:
                    public_verified = bool(_PUBLIC_VERIFY_CACHE.get("ok"))
                else:
                    public_verified = verify_public_endpoint(funnel_host, timeout=2.0)
                    _PUBLIC_VERIFY_CACHE.update(host=funnel_host, ok=public_verified, ts=now)
        except Exception:
            public_verified = False
        if public_verified:
            connectivity = "connected"
            hint = "Local and public MCP endpoints look healthy."
        else:
            if running and active:
                connectivity = "connected"
                hint = (
                    "Funnel is active. Public probe timed out — local MCP is usable; "
                    "retry Repair if public clients fail."
                )
            else:
                connectivity = "degraded"
                hint = (
                    "Funnel is published but the public URL is not responding yet. "
                    "Wait a few seconds or click Repair connection."
                )'''
    if old in t:
        t = t.replace(old, new, 1)
        print("setup.py: public verify cache applied")
    elif "Fast public check with short TTL" in t:
        print("setup.py: already patched")
    else:
        print("setup.py: status block not found")
    path.write_text(t, encoding="utf-8")


def patch_app() -> None:
    path = ROOT / "ui" / "src" / "App.tsx"
    t = path.read_text(encoding="utf-8")
    t = re.sub(
        r'(typeof __APP_VERSION__ !== "undefined" \? __APP_VERSION__ : ")[^"]+(")',
        r"\g<1>2.0.4\2",
        t,
        count=1,
    )
    if "async function apiFetch" not in t:
        helper = '''
/** fetch with timeout + clearer network errors (WebKit "TypeError: Load failed"). */
async function apiFetch(url: string, init: RequestInit = {}, timeoutMs = 12000): Promise<Response> {
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...init, signal: ctrl.signal, cache: init.cache ?? "no-store" });
    return r;
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("Load failed") || msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("aborted") || msg.includes("AbortError")) {
      throw new Error(
        "Cannot reach the Dana setup service (" + msg + "). " +
        "The local control API may have stopped — click Refresh or restart Dana."
      );
    }
    throw e instanceof Error ? e : new Error(String(e));
  } finally {
    window.clearTimeout(timer);
  }
}

'''
        t = t.replace(
            'const API = (p: number, path: string) => "http://127.0.0.1:" + p + path;\n',
            'const API = (p: number, path: string) => "http://127.0.0.1:" + p + path;\n' + helper,
            1,
        )
        if "async function apiFetch" not in t:
            t = t.replace(
                'const API = (p: number, path: string) => "http://127.0.0.1:" + p + path;\n',
                'const API = (p: number, path: string) => "http://127.0.0.1:" + p + path;\n' + helper,
                1,
            )
        print("App.tsx: apiFetch added")

    old_refresh = '''      const r = await fetch(API(p, "/api/setup/status"), { cache: "no-store" });
      const x = await r.json();
      if (!r.ok) throw Error(x.message || x.error);'''
    new_refresh = '''      let r: Response;
      try {
        r = await apiFetch(API(p, "/api/setup/status"), { cache: "no-store" }, 10000);
      } catch (netErr) {
        try {
          const fresh = await resolveSetupPort();
          if (fresh && fresh !== p) {
            setPort(fresh);
            p = fresh;
          }
          r = await apiFetch(API(p, "/api/setup/status"), { cache: "no-store" }, 10000);
        } catch {
          throw netErr;
        }
      }
      const x = await r.json();
      if (!r.ok) throw Error(x.message || x.error);'''
    if old_refresh in t:
        t = t.replace(old_refresh, new_refresh, 1)
        print("App.tsx: refresh reconnect")

    old_run = '''      const r = await fetch(API(port, path), { method: "POST" });
      const x = await r.json();'''
    new_run = '''      let activePort = port;
      let r: Response;
      try {
        r = await apiFetch(API(activePort, path), { method: "POST" }, 60000);
      } catch (netErr) {
        try {
          const fresh = await resolveSetupPort();
          if (fresh) {
            setPort(fresh);
            activePort = fresh;
          }
          r = await apiFetch(API(activePort, path), { method: "POST" }, 60000);
        } catch {
          throw netErr;
        }
      }
      const x = await r.json();'''
    if old_run in t:
        t = t.replace(old_run, new_run, 1)
        print("App.tsx: run reconnect")

    t = t.replace(
        '? "Configuration in progress"\n                    : "Starting service…"',
        '? (status ? "Setup in progress" : "Reconnecting control API…")\n                    : "Starting service…"',
    )
    t = t.replace(
        '? "Setup required"\n                    : "Connecting…"',
        '? (status ? "Setup required" : "API offline — refresh")\n                    : "Connecting…"',
    )
    path.write_text(t, encoding="utf-8")
    print("App.tsx written")


def patch_icons() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("icons: pillow missing, skip")
        return
    src = ROOT / "docs" / "ui" / "dana-logo.png"
    if not src.exists():
        print("icons: png missing")
        return
    im = Image.open(src).convert("RGBA")
    icons = ROOT / "ui" / "src-tauri" / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    sizes = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 256,
        "Square30x30Logo.png": 30,
        "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71,
        "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107,
        "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150,
        "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310,
        "StoreLogo.png": 50,
    }
    for name, size in sizes.items():
        im.resize((size, size), Image.Resampling.LANCZOS).save(icons / name)
    im.save(icons / "icon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icons: regenerated from dana-logo.png")


def bump_version() -> None:
    (ROOT / "dana" / "__init__.py").write_text('__version__ = "2.0.4"\n', encoding="utf-8")
    for f, pat, rep in [
        (ROOT / "pyproject.toml", r'^version = "[^"]+"', 'version = "2.0.4"'),
        (ROOT / "ui" / "package.json", r'"version":\s*"[^"]+"', '"version": "2.0.4"'),
        (ROOT / "ui" / "src-tauri" / "tauri.conf.json", r'"version":\s*"[^"]+"', '"version": "2.0.4"'),
        (ROOT / "ui" / "src-tauri" / "Cargo.toml", r'^version = "[^"]+"', 'version = "2.0.4"'),
    ]:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        f.write_text(re.sub(pat, rep, text, count=1, flags=re.M), encoding="utf-8")
    print("version -> 2.0.4")


def main() -> None:
    patch_setup()
    patch_app()
    patch_icons()
    bump_version()
    print("done")


if __name__ == "__main__":
    main()
