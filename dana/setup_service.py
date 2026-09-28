from __future__ import annotations
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from . import setup

class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: dict[str, object], code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/setup/status":
            self._send(setup.status().to_dict()); return
        if urlparse(self.path).path == "/api/setup/usage":
            self._send(setup.token_usage()); return
        if urlparse(self.path).path == "/api/setup/logs":
            self._send(setup.setup_logs()); return
        self._send({"error": "not_found"}, 404)
    def do_POST(self) -> None:
        action = {
            "/api/setup/install-tailscale": setup.install_tailscale,
            "/api/setup/login-tailscale": setup.login_tailscale,
            "/api/setup/enable-funnel": setup.enable_funnel,
            "/api/setup/start-dana": setup.start_dana,
            "/api/setup/bootstrap": setup.bootstrap,
        }.get(urlparse(self.path).path)
        if not action:
            self._send({"error": "not_found"}, 404); return
        try:
            self._send(action())
        except Exception as exc:
            setup._setup_log(f"Unhandled setup error: {exc}", "error")
            self._send({"ok": False, "message": str(exc)}, 500)
    def log_message(self, _format: str, *_args: object) -> None:
        return

def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="dana-setup-api").start()
    return server

if __name__ == "__main__":
    if "--serve" in sys.argv:
        from .main import run
        run()
    else:
        server = serve()
        port = str(server.server_address[1])
        port_file = os.environ.get("DANA_SETUP_PORT_FILE")
        if port_file:
            from pathlib import Path
            target = Path(port_file)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(port, encoding="ascii")
            temporary.replace(target)
        print(f"DANA_SETUP_PORT={port}", flush=True)
        server.serve_forever()
