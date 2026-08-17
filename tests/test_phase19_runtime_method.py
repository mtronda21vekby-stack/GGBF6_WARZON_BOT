from fastapi.testclient import TestClient

from app.webhook import app


def test_runtime_endpoint_accepts_production_post_probe():
    response = TestClient(app).post("/webapp/api/runtime")
    assert response.status_code == 200
