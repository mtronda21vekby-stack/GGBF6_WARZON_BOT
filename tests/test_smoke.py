from fastapi.testclient import TestClient

from app.webhook import app


def test_app_import_and_core_routes():
    assert app.title == "GGBF6 WARZON BOT"
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["ok"] is True

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"ok": True, "status": "alive"}

    webapp = client.get("/webapp")
    assert webapp.status_code == 200
