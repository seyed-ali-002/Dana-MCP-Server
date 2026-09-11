from dana.server import mcp

from fastapi.testclient import TestClient

from dana.config import settings
from dana.http import app


def test_connector_requires_auth(monkeypatch):
    monkeypatch.setattr("dana.http.settings.public_host", "example.ts.net")
    monkeypatch.setattr("dana.http.settings.public_port", 443)
    with TestClient(app) as client:
        assert client.get("/connector").status_code == 401
        response = client.get(
            "/connector", headers={"Authorization": f"Bearer {settings.auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Chatbot Connection Link"
        assert data["url"] == f"https://example.ts.net/{settings.auth_token}/mcp"
        mcp_response = client.get(f"/{settings.auth_token}/mcp", follow_redirects=False)
        assert mcp_response.status_code == 200
        assert mcp_response.json()["protocol"] == "streamable-http"


def test_local_mode_tokenized_mcp_path_remains_available_without_bearer(monkeypatch):
    monkeypatch.setattr("dana.http.settings.deployment_mode", "local")
    with TestClient(app) as client:
        response = client.get(f"/{settings.auth_token}/mcp", follow_redirects=False)
        assert response.status_code == 200
        assert response.json()["endpoint"].endswith("/mcp")
        root = client.get("/mcp", follow_redirects=False)
        assert root.status_code == 401


def test_mcp_requires_oauth_bearer_and_advertises_discovery_metadata():
    with TestClient(app) as client:
        response = client.get("/mcp", follow_redirects=False)
        assert response.status_code == 401
        assert "resource_metadata=" in response.headers["www-authenticate"]
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json()["resource"].endswith("/mcp")



def test_mcp_get_probe_is_not_rejected_for_missing_accept():
    with TestClient(app) as client:
        response = client.get("/mcp", follow_redirects=False)
        assert response.status_code == 401


def test_mcp_get_accept_header_compatibility():
    with TestClient(app) as client:
        response = client.get(
            "/mcp", headers={"Accept": "application/json"}, follow_redirects=False
        )
        assert response.status_code == 401



def test_oauth_token_uses_long_lived_static_credential():
    assert settings.oauth_access_token_ttl_seconds >= 31_536_000


def test_server_mode_connector_uses_canonical_https_url(monkeypatch):
    monkeypatch.setattr("dana.http.settings.deployment_mode", "server")
    monkeypatch.setattr("dana.http.settings.public_host", "mcp.example.com")
    monkeypatch.setattr("dana.http.settings.public_port", 0)
    try:
        with TestClient(app) as client:
            response = client.get(
                "/connector", headers={"Authorization": f"Bearer {settings.auth_token}"}
            )
            assert response.status_code == 200
            assert response.json()["url"] == "https://mcp.example.com/mcp"
    finally:
        monkeypatch.setattr("dana.http.settings.deployment_mode", "local")


def test_server_mode_mcp_uses_canonical_path(monkeypatch):
    monkeypatch.setattr("dana.http.settings.deployment_mode", "server")
    try:
        with TestClient(app) as client:
            response = client.get("/mcp", follow_redirects=False)
            assert response.status_code == 401
            legacy = client.get(f"/{settings.auth_token}/mcp", follow_redirects=False)
            assert legacy.status_code in {404, 401}
    finally:
        monkeypatch.setattr("dana.http.settings.deployment_mode", "local")


def test_server_mode_connector_uses_single_canonical_url(monkeypatch):
    monkeypatch.setattr("dana.http.settings.deployment_mode", "server")
    monkeypatch.setattr("dana.http.settings.public_host", "mcp.example.com")
    try:
        with TestClient(app) as client:
            response = client.get(
                "/connector", headers={"Authorization": f"Bearer {settings.auth_token}"}
            )
            assert (
                response.json()["url"]
                == "https://mcp.example.com/mcp"
            )
    finally:
        monkeypatch.setattr("dana.http.settings.deployment_mode", "local")



def test_mcp_streamable_http_lifecycle_initializes_task_group():
    with TestClient(app) as client:
        response = client.get(
            "/mcp",
            headers={"Accept": "text/event-stream", "Authorization": f"Bearer {settings.auth_token}"},
            follow_redirects=False,
        )
        assert response.status_code != 500


def test_mcp_transport_can_restart_with_a_fresh_session_manager():
    for _ in range(2):
        with TestClient(app) as client:
            response = client.get("/mcp", headers={"Authorization": f"Bearer {settings.auth_token}"}, follow_redirects=False)
            assert response.status_code != 500



def test_authorize_accepts_supported_connector_callback_origins():
    from dana.http import _is_trusted_connector_redirect_uri

    # OpenAI / ChatGPT
    assert _is_trusted_connector_redirect_uri("https://chatgpt.com/connector/oauth/callback")
    assert _is_trusted_connector_redirect_uri("https://chat.openai.com/connector/oauth/callback")
    assert _is_trusted_connector_redirect_uri("https://openai.com/connector/oauth/callback")

    # Anthropic / Claude
    assert _is_trusted_connector_redirect_uri("https://claude.ai/oauth/callback")
    assert _is_trusted_connector_redirect_uri("https://console.anthropic.com/oauth/callback")

    # xAI / Grok
    assert _is_trusted_connector_redirect_uri("https://grok.com/oauth/callback")
    assert _is_trusted_connector_redirect_uri("https://console.x.ai/oauth/callback")
    assert _is_trusted_connector_redirect_uri("https://x.com/oauth/callback")

    # Reject insecure and look-alike origins.
    assert not _is_trusted_connector_redirect_uri("http://grok.com/oauth/callback")
    assert not _is_trusted_connector_redirect_uri("https://claude.ai.evil.example/callback")
