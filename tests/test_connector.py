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
        mcp_response = client.get(f"/{settings.auth_token}/mcp", follow_redirects=False)
        assert mcp_response.status_code != 401



