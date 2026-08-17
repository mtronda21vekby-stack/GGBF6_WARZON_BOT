from fastapi.testclient import TestClient

from app.webhook import app


def test_health_details_reports_v19_and_mission_control():
    response = TestClient(app).get("/health/details")
    assert response.status_code == 200
    payload = response.json()
    assert payload["release"]["version"] == "19.0.0"
    assert payload["features"]["adaptive_mission_control"] is True
