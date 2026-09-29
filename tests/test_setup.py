from __future__ import annotations
import json
from dana import setup

def test_setup_status_shape(monkeypatch):
    monkeypatch.setattr(setup, "command_exists", lambda _name: False)
    monkeypatch.setattr(setup, "_dana_running", lambda: False)
    result = setup.status().to_dict()
    assert result["tailscale_installed"] is False
    assert result["action_required"] == "install_tailscale"

def test_setup_status_requires_login(monkeypatch):
    monkeypatch.setattr(setup, "command_exists", lambda _name: True)
    monkeypatch.setattr(setup, "_run", lambda *args, **kwargs: type("R", (), {"returncode": 0, "stdout": json.dumps({"BackendState": "NeedsLogin", "Self": {}}), "stderr": ""})())
    monkeypatch.setattr(setup, "_funnel_active", lambda: False)
    monkeypatch.setattr(setup, "_dana_running", lambda: False)
    assert setup.status().action_required == "login_tailscale"

def test_auth_url_detection():
    assert setup._find_auth_url("https://login.tailscale.com/a/abc123") == "https://login.tailscale.com/a/abc123"

def test_stable_package_urls(monkeypatch):
    html = '<a href="tailscale-setup-1.102.4.exe">Windows</a><a href="Tailscale-1.102.4-macos.pkg">macOS</a>'
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return html.encode()
    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    win, mac = setup._stable_package_urls()
    assert win.endswith("tailscale-setup-1.102.4.exe")
    assert mac.endswith("Tailscale-1.102.4-macos.pkg")

def test_funnel_configuration_uses_current_cli_shape(monkeypatch):
    calls = []
    monkeypatch.setattr(setup, "_ensure_tailscale_ready", lambda: None)
    monkeypatch.setattr(setup, "configure_tailscale_local", lambda token, port, funnel_port: calls.append((token, port, funnel_port)) or "dana.example.ts.net")
    monkeypatch.setattr(setup, "verify_public_endpoint", lambda host: True)
    result = setup.enable_funnel(8765)
    assert result["ok"] is True
    assert len(calls) == 1
    assert calls[0][1:] == (8765, 443)


def test_public_endpoint_accepts_authenticated_mcp_response(monkeypatch):
    class Response:
        status = 401
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert setup.verify_public_endpoint("dana.example.ts.net") is True



def test_configuration_exposes_runtime_defaults(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(setup, "_env_path", lambda: env_file)
    monkeypatch.setattr(setup.settings, "host", "127.0.0.1")
    monkeypatch.setattr(setup.settings, "port", 8765)
    monkeypatch.setattr(setup.settings, "mcp_path", "/mcp")
    monkeypatch.setattr(setup.settings, "allow_dangerous_tools", False)
    monkeypatch.setattr(setup.settings, "tailscale_funnel_enabled", True)
    data = setup.configuration()
    assert data["values"]["DANA_PORT"] == "8765"
    assert data["values"]["DANA_MCP_PATH"] == "/mcp"
    assert data["values"]["DANA_ALLOW_DANGEROUS_TOOLS"] == "false"
    assert data["values"]["DANA_TAILSCALE_FUNNEL_ENABLED"] == "true"


def test_token_is_not_rotated_by_startup_write_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    existing = "DANA_AUTH_TOKEN=stable-token-value-123456\n"
    env_file.write_text(existing, encoding="utf-8")
    monkeypatch.setattr("dana.installer.ROOT", tmp_path)
    token = __import__("dana.installer", fromlist=["write_env"]).write_env("local", workers=5)
    assert token == "stable-token-value-123456"
    assert "DANA_AUTH_TOKEN=stable-token-value-123456" in env_file.read_text(encoding="utf-8")
