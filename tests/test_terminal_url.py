from dana import main


def test_local_terminal_url_is_stable_tokenized_contract(monkeypatch):
    monkeypatch.setattr(main.settings, "deployment_mode", "local")
    monkeypatch.setattr(main.settings, "public_host", "dana.example.ts.net")
    monkeypatch.setattr(main.settings, "public_port", 443)
    monkeypatch.setattr(main.settings, "mcp_path", "/mcp")
    monkeypatch.setattr(main.settings, "auth_token", "stable-token-123456789")

    assert main._public_url() == "https://dana.example.ts.net/stable-token-123456789/mcp"


def test_local_terminal_url_preserves_nonstandard_public_port(monkeypatch):
    monkeypatch.setattr(main.settings, "deployment_mode", "local")
    monkeypatch.setattr(main.settings, "public_host", "dana.example.ts.net")
    monkeypatch.setattr(main.settings, "public_port", 8443)
    monkeypatch.setattr(main.settings, "mcp_path", "/mcp")
    monkeypatch.setattr(main.settings, "auth_token", "stable-token-123456789")

    assert main._public_url() == "https://dana.example.ts.net:8443/stable-token-123456789/mcp"
