from fastapi.testclient import TestClient

from app.webhook import app


def test_telegram_duplicate_update_is_acknowledged_without_reprocessing():
    client = TestClient(app)
    payload = {"update_id": 991_771_001}

    first = client.post("/tg/webhook", json=payload)
    second = client.post("/tg/webhook", json=payload)

    assert first.status_code == 200
    assert first.json()["ok"] is True
    assert second.status_code == 200
    assert second.json() == {"ok": True, "duplicate": True}


def test_telegram_update_payload_has_hard_size_cap():
    client = TestClient(app)
    response = client.post(
        "/tg/webhook",
        content=b"x" * (300 * 1024),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_readiness_exposes_only_aggregate_guard_state():
    client = TestClient(app)
    response = client.get("/health/details")
    assert response.status_code == 200
    payload = response.json()
    assert payload["features"]["abuse_guard"] is True
    assert payload["features"]["telegram_replay_dedupe"] is True
    assert payload["abuse_guard"]["telegram_max_update_bytes"] == 256 * 1024
    rendered = repr(payload["abuse_guard"])
    assert "subject:" not in rendered
