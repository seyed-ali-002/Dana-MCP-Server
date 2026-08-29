from fastapi.testclient import TestClient

from dana.http import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"



def test_health_reports_mode() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.json()["mode"] in {"local", "server"}



def test_health_default_mode_is_valid() -> None:
    from dana.config import settings
    assert settings.normalized_mode() in {"local", "server"}
