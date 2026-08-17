from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.webhook import app


def test_runtime_contract_is_v19_and_privacy_safe():
    client = TestClient(app)
    response = client.post("/webapp/api/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["release"] == "bco-adaptive-mission-control-v19"
    assert payload["webapp"]["adaptive_mission_control"] is True
    assert payload["webapp"]["live_stream"] is True
    assert payload["webapp"]["cinematic_ui"] is True
    assert payload["webapp"]["transport"] == "ndjson"
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "BOT_TOKEN",
        "OPENAI_API_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "initData",
        "service_role",
    ):
        assert forbidden not in serialized
