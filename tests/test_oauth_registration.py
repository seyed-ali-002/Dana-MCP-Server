from fastapi.testclient import TestClient

from dana.http import app


def test_oauth_metadata_advertises_dynamic_client_registration(monkeypatch):
    monkeypatch.setattr("dana.http.settings.public_host", "mcp.example.com")
    with TestClient(app) as client:
        metadata = client.get("/.well-known/oauth-authorization-server")
        assert metadata.status_code == 200
        assert metadata.json()["registration_endpoint"] == "https://mcp.example.com/register"


def test_dynamic_client_registration_and_authorize_flow():
    with TestClient(app) as client:
        registration = client.post(
            "/register",
            json={
                "client_name": "ChatGPT",
                "redirect_uris": ["https://chatgpt.com/connector/oauth/callback"],
                "token_endpoint_auth_method": "none",
            },
        )
        assert registration.status_code == 201
        client_id = registration.json()["client_id"]
        response = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "https://chatgpt.com/connector/oauth/callback",
                "code_challenge": "abc",
                "code_challenge_method": "S256",
                "state": "test",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


def test_dynamic_client_registration_rejects_untrusted_redirect():
    with TestClient(app) as client:
        response = client.post(
            "/register",
            json={"redirect_uris": ["https://evil.example/callback"]},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_redirect_uri"
