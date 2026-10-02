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
    monkeypatch.setattr(setup, "_funnel_status", lambda: (True, "dana.example.ts.net"))
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
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "home")
    token = __import__("dana.installer", fromlist=["write_env"]).write_env("local", workers=5)
    assert token == "stable-token-value-123456"
    assert "DANA_AUTH_TOKEN=stable-token-value-123456" in env_file.read_text(encoding="utf-8")




def test_startup_write_env_keeps_persistent_token(monkeypatch, tmp_path):
    root = tmp_path / "install"
    home = tmp_path / "home"
    root.mkdir()
    persistent = home / ".config" / "dana"
    persistent.mkdir(parents=True)
    persistent.joinpath(".env").write_text("DANA_AUTH_TOKEN=persistent-stable-token-123456\n", encoding="utf-8")
    monkeypatch.setattr("dana.installer.ROOT", root)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    first = __import__("dana.installer", fromlist=["write_env"]).write_env("local", workers=5)
    second = __import__("dana.installer", fromlist=["write_env"]).write_env("local", workers=5)
    assert first == "persistent-stable-token-123456"
    assert second == first
    assert "DANA_AUTH_TOKEN=persistent-stable-token-123456" in (root / ".env").read_text(encoding="utf-8")



def test_persistent_token_is_authoritative_over_install_env(monkeypatch, tmp_path):
    root = tmp_path / "install"
    home = tmp_path / "home"
    root.mkdir()
    persistent = home / ".config" / "dana"
    persistent.mkdir(parents=True)
    (root / ".env").write_text("DANA_AUTH_TOKEN=old-install-token-123456\n", encoding="utf-8")
    (persistent / ".env").write_text("DANA_AUTH_TOKEN=persistent-token-123456\n", encoding="utf-8")
    monkeypatch.setattr(setup, "_env_path", lambda: root / ".env")
    monkeypatch.setattr(setup, "_persistent_env_path", lambda: persistent / ".env")
    values = setup._read_env()
    assert values["DANA_AUTH_TOKEN"] == "persistent-token-123456"



def test_auth_flow_status_is_persistent_and_clearable():
    setup._set_auth_flow("login", "https://login.tailscale.com/a/test", "Complete login", True)
    pending = setup.auth_flow_status()
    assert pending["pending"] is True
    assert pending["kind"] == "login"
    setup._set_auth_flow()
    assert setup.auth_flow_status()["pending"] is False


def test_tailscale_download_falls_back_after_403(monkeypatch, tmp_path):
    calls = []
    class Response:
        headers = {"Content-Length": "4"}
        def __init__(self): self.done = False
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, _size=0):
            if self.done: return b""
            self.done = True
            return b"test"
    def fake_open(request, timeout=0):
        import urllib.error
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)
        return Response()
    class Opener:
        def open(self, request, timeout=0):
            return fake_open(request, timeout)
    monkeypatch.setattr(setup.urllib.request, "build_opener", lambda *args, **kwargs: Opener())
    target = tmp_path / "installer.sh"
    setup._download_file(setup.TAILSCALE_INSTALL_SCRIPT, target, "Tailscale installer")
    assert target.read_bytes() == b"test"
    assert len(calls) == 2
    assert "githubusercontent.com" in calls[1]



def test_tailscale_static_urls_use_newest_architecture_and_mirror(monkeypatch):
    html = '''
      <a href="tailscale_1.101.0_amd64.tgz">old</a>
      <a href="tailscale_1.102.4_amd64.tgz">new</a>
    '''
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return html.encode()
    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    urls = setup._static_tailscale_urls("amd64")
    assert urls[0].endswith("tailscale_1.102.4_amd64.tgz")
    assert "github.com/tailscale/tailscale/releases/download/v1.102.4/" in urls[1]


def test_tailscale_static_architecture_mapping(monkeypatch):
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    assert setup._tailscale_static_arch() == "amd64"
    monkeypatch.setattr(setup.platform, "machine", lambda: "aarch64")
    assert setup._tailscale_static_arch() == "arm64"


def test_stop_dana_does_not_touch_funnel_or_request_privilege(monkeypatch):
    calls = []
    monkeypatch.setattr(setup, "_DANA_PROCESS", None)
    monkeypatch.setattr(setup, "_dana_running", lambda: False)
    monkeypatch.setattr(setup, "_privileged_run", lambda *args, **kwargs: calls.append(args) or (_ for _ in ()).throw(AssertionError("privileged Funnel command must not run")))
    from dana import container
    monkeypatch.setattr(container, "is_available", lambda: False)
    result = setup.stop_dana()
    assert result["ok"] is True
    assert calls == []


def test_restart_runtime_does_not_reconfigure_existing_funnel(monkeypatch):
    sequence = iter([True, True])
    monkeypatch.setattr(setup, "_funnel_active", lambda: next(sequence))
    calls = {"stop": 0, "start": 0, "enable": 0}
    monkeypatch.setattr(setup, "stop_dana", lambda: calls.__setitem__("stop", calls["stop"] + 1) or {"ok": True})
    monkeypatch.setattr(setup, "start_dana", lambda: calls.__setitem__("start", calls["start"] + 1) or {"ok": True})
    monkeypatch.setattr(setup, "enable_funnel", lambda *_args, **_kwargs: calls.__setitem__("enable", calls["enable"] + 1) or {"ok": True})
    result = setup._restart_runtime_preserving_funnel()
    assert result["ok"] is True
    assert calls == {"stop": 1, "start": 1, "enable": 0}
