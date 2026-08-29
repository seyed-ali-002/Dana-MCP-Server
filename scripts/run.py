#!/usr/bin/env python3
from __future__ import annotations
import os, re, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
from rich.console import Console
from rich.panel import Panel


ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.getenv("DANA_PORT", "8765"))
console = Console()


def banner():
    console.print(Panel.fit("[bold cyan]DANA[/bold cyan]\n[dim]MCP Server Installer & Launcher[/dim]", border_style="cyan"))

def run(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)

def main():
    banner()
    mode = os.getenv("DANA_DEPLOYMENT_MODE", "local").lower().strip()
    if mode != "local":
        raise SystemExit("This launcher is for Local Mode. Run the installer and select Server Mode for public-server deployment.")
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
        # Add Dana under its own Funnel path so an existing Funnel root route is untouched.
        run(["tailscale", "funnel", "--set-path", f"/{token}", "--bg", f"http://127.0.0.1:{PORT}"])
        status = subprocess.check_output(["tailscale", "funnel", "status"], text=True)
        m = re.search(r"https://[^\s]+", status)
        if not m:
            raise RuntimeError("Could not determine Tailscale Funnel URL")
        url = m.group(0).rstrip("/")
        connector_url = f"{url}/{token}/mcp"
        console.clear()
        console.print(Panel.fit("[bold green]DANA IS READY[/bold green]\n[dim]Press Ctrl+C to stop.[/dim]", border_style="green"))
        console.print(f"[bold cyan]Connector URL:[/bold cyan] {connector_url}")
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=5)

if __name__ == "__main__": main()
