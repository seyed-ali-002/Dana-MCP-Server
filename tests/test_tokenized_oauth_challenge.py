from fastapi.testclient import TestClient

from dana.config import settings
from dana.http import app


def _tokenized_path() -> str:
    return f"/{settings.require_auth_token()}{settings.mcp_path}"


def test_tokenized_mcp_returns_oauth_challenge_without_bearer():
    with TestClient(app) as client:
        response = client.post(
            _tokenized_path(),
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert response.status_code == 401
        challenge = response.headers["www-authenticate"]
        assert "resource_metadata=" in challenge
        assert settings.require_auth_token() in challenge
        assert settings.mcp_path in challenge


def test_tokenized_mcp_challenges_mcp_get_without_bearer():
    with TestClient(app) as client:
        response = client.get(
            _tokenized_path(),
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert response.status_code == 401
        assert "resource_metadata=" in response.headers["www-authenticate"]


def test_tokenized_mcp_browser_probe_is_not_unauthorized():
    with TestClient(app) as client:
        response = client.get(_tokenized_path(), headers={"Accept": "text/html"})
        assert response.status_code == 200
        assert response.json()["protocol"] == "streamable-http"


def test_tokenized_mcp_accepts_dana_bearer():
    with TestClient(app) as client:
        response = client.get(
            _tokenized_path(),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.require_auth_token()}",
            },
        )
        assert response.status_code == 200
