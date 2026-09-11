from fastapi.testclient import TestClient

from dana.config import settings
from dana.http import app


def _tokenized_path() -> str:
    return f"/{settings.require_auth_token()}{settings.mcp_path}"


def test_local_tokenized_resource_keeps_existing_url_shape():
    assert _tokenized_path().endswith("/mcp")


def test_local_tokenized_oauth_metadata_rfc_discovery():
    token_path = _tokenized_path()
    with TestClient(app) as client:
        response = client.get(f"/.well-known/oauth-protected-resource{token_path}")
        assert response.status_code == 200
        assert response.json()["resource"].endswith(token_path)
        assert response.json()["authorization_servers"]


def test_local_tokenized_oauth_metadata_path_local_alias():
    token = settings.require_auth_token()
    with TestClient(app) as client:
        response = client.get(f"/{token}/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        assert response.json()["resource"].endswith(_tokenized_path())


def test_tokenized_authorization_server_alias():
    token = settings.require_auth_token()
    with TestClient(app) as client:
        response = client.get(f"/{token}/.well-known/oauth-authorization-server")
        assert response.status_code == 200
        assert response.json()["registration_endpoint"].endswith("/register")
