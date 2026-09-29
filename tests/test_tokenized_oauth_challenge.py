from fastapi.testclient import TestClient

from dana.config import settings
from dana.http import app


def _tokenized_path() -> str:
    return f"/{settings.require_auth_token()}{settings.mcp_path}"


def test_tokenized_mcp_authenticates_without_bearer():
    with TestClient(app) as client:
        response = client.post(
            _tokenized_path(),
            headers={"Host": "127.0.0.1", "Accept": "application/json", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
        )
        assert response.status_code == 200
        assert "protocolVersion" in response.text


def test_wrong_tokenized_path_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/wrong-token/mcp",
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert response.status_code in {401, 404}


def test_tokenized_mcp_get_accepts_url_token():
    with TestClient(app) as client:
        response = client.get(
            _tokenized_path(),
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert response.status_code != 401


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


def test_connector_link_contains_tokenized_local_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/connector",
            headers={"Authorization": f"Bearer {settings.require_auth_token()}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["url"].endswith(f"/{settings.require_auth_token()}{settings.mcp_path}")
        assert settings.require_auth_token() in payload["url"]
        assert "Bearer" in payload["authentication"]


def test_public_connection_url_requires_oauth_bearer():
    with TestClient(app) as client:
        response = client.post(
            settings.mcp_path,
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert response.status_code == 401
        assert "resource_metadata=" in response.headers["www-authenticate"]



def test_tokenized_mcp_initialize_handshake():
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "dana-test", "version": "1.0"},
        },
    }
    with TestClient(app) as client:
        response = client.post(
            f"/{settings.require_auth_token()}{settings.mcp_path}",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Host": settings.public_host or "127.0.0.1",
            },
            json=body,
        )
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "") or "text/event-stream" in response.headers.get("content-type", "")
        payload = response.json() if "application/json" in response.headers.get("content-type", "") else {}
        if payload:
            assert payload.get("result", {}).get("serverInfo", {}).get("name")
