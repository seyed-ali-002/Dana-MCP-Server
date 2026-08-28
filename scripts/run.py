#!/usr/bin/env python3
from __future__ import annotations
import os, re, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.getenv("DANA_PORT", "8765"))

def run(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)

def main():
    if not shutil.which("tailscale"):
        raise SystemExit("Tailscale is not installed or not in PATH.")
    py = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not py.exists():
        run([sys.executable, "-m", "venv", ".venv"])
        py = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    run([str(py), "-m", "pip", "install", "-e", ".[dev]"])
    token = subprocess.check_output([str(py), "scripts/init_token.py"], cwd=ROOT, text=True).strip().splitlines()[-1]
    server = subprocess.Popen([str(py), "-m", "dana.main"], cwd=ROOT)
    try:
        healthy = False
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as r:
                    if r.status == 200:
                        healthy = True
                        break
            except Exception:
                time.sleep(.5)
        if not healthy:
            raise RuntimeError("Dana health check failed")
        run(["tailscale", "funnel", "--bg", f"http://127.0.0.1:{PORT}"])
        status = subprocess.check_output(["tailscale", "funnel", "status"], text=True)
        m = re.search(r"https://[^\s]+", status)
        if not m:
            raise RuntimeError("Could not determine Tailscale Funnel URL")
        url = m.group(0).rstrip("/") + "/mcp"
        print(f"\nMCP Connector URL: {url}", flush=True)
        print(f"Bearer Token: {token}", flush=True)
        print("\nPress Ctrl+C to stop.", flush=True)
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=5)

if __name__ == "__main__": main()
