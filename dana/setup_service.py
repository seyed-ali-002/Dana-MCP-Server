from __future__ import annotations
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from dana import setup

class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: dict[str, object], code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionError, BrokenPipeError, OSError) as exc:
            # Windows often raises WinError 10053/10054 when the UI aborts a long
            # setup request. Log softly; the action may still have completed.
            setup._setup_log(f"Setup client connection closed while responding: {exc}", "warning")
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/setup/status":
            self._send(setup.status().to_dict()); return
        if urlparse(self.path).path == "/api/setup/auth-flow":
            self._send(setup.auth_flow_status()); return
        if urlparse(self.path).path == "/api/setup/usage":
            self._send(setup.token_usage()); return
        if urlparse(self.path).path == "/api/setup/logs":
            self._send(setup.setup_logs()); return
        if urlparse(self.path).path == "/api/setup/activity":
            self._send(setup.runtime_activity()); return
        if urlparse(self.path).path == "/api/setup/download":
            self._send(setup.download_status()); return
        if urlparse(self.path).path == "/api/setup/config":
            self._send(setup.configuration()); return
        if urlparse(self.path).path == "/api/setup/connection-test":
            try:
                self._send(setup.test_connections())
            except Exception as exc:
                self._send({"ok": False, "message": str(exc)}, 400)
            return

        self._send({"error": "not_found"}, 404)
    def do_POST(self) -> None:
        action = {
            "/api/setup/install-tailscale": setup.install_tailscale,
            "/api/setup/login-tailscale": setup.login_tailscale,
            "/api/setup/enable-funnel": setup.enable_funnel,
            "/api/setup/start-dana": setup.start_dana,
            "/api/setup/stop-dana": setup.stop_dana,
            "/api/setup/bootstrap": setup.bootstrap,
        }.get(urlparse(self.path).path)
        request_path = urlparse(self.path).path
        if request_path == "/api/setup/download/pause":
            self._send(setup.pause_download()); return
        if request_path == "/api/setup/download/resume":
            self._send(setup.resume_download()); return
        if request_path == "/api/setup/download/cancel":
            self._send(setup.cancel_download()); return
        if request_path in {"/api/setup/security/revoke-token", "/api/setup/security/token", "/api/setup/config"}:
            try:
                if request_path == "/api/setup/security/revoke-token":
                    self._send(setup.set_auth_token("", revoke=True)); return
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8") or "{}")
                if request_path == "/api/setup/security/token":
                    self._send(setup.set_auth_token(str(payload.get("token", "")))); return
                values = payload.get("values", payload)
                if not isinstance(values, dict):
                    raise ValueError("Configuration values must be an object")
                self._send(setup.update_configuration(values)); return
            except Exception as exc:
                setup._setup_log(f"Configuration/security action failed: {exc}", "error")
                self._send({"ok": False, "message": str(exc)}, 400)
                return

        if not action:
            self._send({"error": "not_found"}, 404); return
        try:
            self._send(action())
        except (ConnectionError, BrokenPipeError, OSError) as exc:
            # Do not treat a dropped HTTP client as a failed setup action.
            setup._setup_log(f"Setup client disconnected during action: {exc}", "warning")
        except Exception as exc:
            setup._setup_log(f"Unhandled setup error: {exc}", "error")
            try:
                self._send({"ok": False, "message": str(exc)}, 500)
            except Exception:
                pass
    def log_message(self, _format: str, *_args: object) -> None:
        return

def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="dana-setup-api").start()
    return server

if __name__ == "__main__":
    if "--serve" in sys.argv:
        from dana.main import run
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
