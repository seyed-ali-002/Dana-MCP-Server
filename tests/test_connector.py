from fastapi.testclient import TestClient

from dana.http import app


def test_connector_requires_auth(monkeypatch):
    monkeypatch.setattr("dana.http.settings.auth_token", "test-token")
    monkeypatch.setattr("dana.http.settings.public_host", "example.ts.net")
    client = TestClient(app)
    assert client.get("/connector").status_code == 401
    response = client.get("/connector", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json() == {
        "url": "https://example.ts.net/mcp",
        "authorization": "Bearer test-token",
    }
