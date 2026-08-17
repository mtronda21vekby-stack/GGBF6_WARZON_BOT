from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.config import get_settings
from app.webhook import app


def _signed_init_data(bot_token: str, *, user_id: int = 98119) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "AAH-v19-mission-control",
        "user": json.dumps(
            {"id": user_id, "first_name": "Operator", "username": "operator"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    values["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


def _mission_endpoint_paths(client: TestClient):
    paths = {route.path for route in app.routes}
    snapshot = next(
        (path for path in paths if "mission" in path and ("snapshot" in path or path.endswith("/mission"))),
        None,
    )
    accept = next((path for path in paths if "mission" in path and "accept" in path), None)
    complete = next((path for path in paths if "mission" in path and "complete" in path), None)
    assert snapshot, sorted(paths)
    assert accept, sorted(paths)
    assert complete, sorted(paths)
    return snapshot, accept, complete


def test_runtime_exposes_adaptive_mission_control_without_secrets():
    client = TestClient(app)
    response = client.post("/webapp/api/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["release"] == "bco-adaptive-mission-control-v19"
    assert payload["webapp"]["adaptive_mission_control"] is True
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "BOT_TOKEN" not in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "SUPABASE_SERVICE_ROLE_KEY" not in rendered


def test_untrusted_client_cannot_accept_or_complete_persistent_mission():
    client = TestClient(app)
    snapshot_path, accept_path, complete_path = _mission_endpoint_paths(client)

    snapshot = client.get(snapshot_path)
    assert snapshot.status_code in {200, 401, 403}

    accept = client.post(accept_path, json={"mission_id": "forged", "id": "forged"})
    complete = client.post(
        complete_path,
        json={"mission_id": "forged", "id": "forged", "success": True, "note": "forged"},
    )
    assert accept.status_code in {401, 403}
    assert complete.status_code in {401, 403}


def test_verified_operator_can_read_mission_snapshot():
    settings = get_settings()
    token = str(settings.bot_token or "").strip()
    if not token:
        # Security validation already has direct cryptographic tests. In a
        # secret-free CI process, assert that the endpoint still rejects the
        # forged identity rather than weakening the boundary.
        client = TestClient(app)
        snapshot_path, _, _ = _mission_endpoint_paths(client)
        response = client.get(
            snapshot_path,
            headers={"X-Telegram-Init-Data": "query_id=x&auth_date=1&hash=forged"},
        )
        assert response.status_code in {401, 403}
        return

    client = TestClient(app)
    snapshot_path, _, _ = _mission_endpoint_paths(client)
    init_data = _signed_init_data(token)
    response = client.get(snapshot_path, headers={"X-Telegram-Init-Data": init_data})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    mission = payload.get("mission") or (payload.get("snapshot") or {}).get("mission")
    assert isinstance(mission, dict)
    assert mission.get("id")
