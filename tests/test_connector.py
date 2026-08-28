from dana.server import mcp

from fastapi.testclient import TestClient

from dana.config import settings
from dana.http import app


def test_connector_requires_auth(monkeypatch):
    monkeypatch.setattr("dana.http.settings.public_host", "example.ts.net")
    with TestClient(app) as client:
        assert client.get("/connector").status_code == 401
        response = client.get("/connector", headers={"Authorization": f"Bearer {settings.auth_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Chatbot Connection Link"
        assert data["url"] == f"https://example.ts.net/{settings.auth_token}/mcp"
        mcp_response = client.get("/mcp", follow_redirects=False)
        assert mcp_response.status_code != 404
        assert mcp_response.status_code != 401
        assert mcp_response.status_code != 400






def test_mcp_get_probe_is_not_rejected_for_missing_accept():
    with TestClient(app) as client:
        response = client.get("/mcp", follow_redirects=False)
        assert response.status_code != 406
        assert response.status_code != 404


def test_mcp_get_accept_header_compatibility():
    with TestClient(app) as client:
        response = client.get("/mcp", headers={"Accept": "application/json"}, follow_redirects=False)
        assert response.status_code != 406
