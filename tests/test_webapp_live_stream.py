from __future__ import annotations

import json
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.webapp import webapp_router as live_router


class StreamingBrain:
    def __init__(self):
        self.calls: list[dict] = []

    def reply(self, *, text, profile, history, on_partial=None):
        self.calls.append({"text": text, "profile": dict(profile), "history": list(history)})
        if on_partial is not None:
            on_partial("Держи высоту.", {"phase": "generating", "attempt": 1})
            time.sleep(0.015)
            on_partial(
                "Держи высоту. Ротируй раньше.",
                {"phase": "candidate", "attempt": 1},
            )
        return "Держи высоту. Ротируй раньше."


class ServerProfiles:
    def get(self, identity: int):
        assert identity == 123
        return {
            "game": "SERVER_WARZONE",
            "platform": "Xbox",
            "input": "Controller",
            "difficulty": "Pro",
            "voice": "COACH",
        }


class ServerStore:
    def get(self, identity: int):
        assert identity == 123
        return [{"role": "assistant", "content": "server history"}]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(live_router.router)
    return app


def _events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _settings(**overrides):
    data = {
        "openai_api_key": "configured",
        "ai_enabled": True,
        "webapp_live_stream_enabled": True,
        "webapp_cinematic_ui_enabled": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_missing_init_data_stream_is_denied_before_generation(monkeypatch):
    brain = StreamingBrain()
    monkeypatch.setattr(live_router._base, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._base, "APP_SETTINGS", _settings())
    monkeypatch.setattr(live_router._base, "APP_PROFILES", None)
    monkeypatch.setattr(live_router._base, "APP_STORE", None)

    response = TestClient(_app()).post(
        "/webapp/api/ask/stream",
        json={
            "text": "Почему поздно ротирую?",
            "profile": {"game": "Warzone", "platform": "Xbox", "admin": True},
            "history": [{"role": "user", "content": "untrusted context"}],
            "initData": "",
        },
        headers={"X-BCO-Version": "test-v18"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "telegram_auth_required"
    assert detail["request_id"]
    assert brain.calls == []


def test_forged_stream_is_denied_before_generation(monkeypatch):
    brain = StreamingBrain()
    monkeypatch.setattr(live_router._base, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._base, "APP_SETTINGS", _settings())
    monkeypatch.setattr(live_router._base, "APP_PROFILES", None)
    monkeypatch.setattr(live_router._base, "APP_STORE", None)
    monkeypatch.setattr(live_router._base, "verify_init_data", lambda _value: (False, {}))

    response = TestClient(_app()).post(
        "/webapp/api/ask/stream",
        json={
            "text": "Use this client history",
            "profile": {"game": "CLIENT_OVERRIDE"},
            "history": [{"role": "assistant", "content": "untrusted history"}],
            "initData": "forged",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "telegram_auth_invalid"
    assert brain.calls == []


def test_trusted_stream_ignores_client_profile_and_uses_server_context(monkeypatch):
    brain = StreamingBrain()
    monkeypatch.setattr(live_router._base, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._base, "APP_SETTINGS", _settings())
    monkeypatch.setattr(live_router._base, "APP_PROFILES", ServerProfiles())
    monkeypatch.setattr(live_router._base, "APP_STORE", ServerStore())
    monkeypatch.setattr(
        live_router._base,
        "verify_init_data",
        lambda _value: (True, {"chat_id": -999, "user_id": 123}),
    )

    response = TestClient(_app()).post(
        "/webapp/api/ask/stream",
        json={
            "text": "Разбери файт",
            "profile": {"game": "CLIENT_OVERRIDE", "difficulty": "Demon"},
            "history": [{"role": "assistant", "content": "client override"}],
            "initData": "trusted",
        },
    )

    assert response.status_code == 200
    final = next(event for event in _events(response) if event["type"] == "final")
    assert final["trusted"] is True
    assert final["meta"]["authority"] == "verified_telegram_server_context"
    assert brain.calls[0]["profile"]["game"] == "SERVER_WARZONE"
    assert brain.calls[0]["history"] == [{"role": "assistant", "content": "server history"}]


def test_runtime_gate_can_roll_back_entire_v18_overlay(monkeypatch):
    monkeypatch.setattr(
        live_router._base,
        "APP_SETTINGS",
        _settings(webapp_live_stream_enabled=False, webapp_cinematic_ui_enabled=True),
    )
    response = TestClient(_app()).post("/webapp/api/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["release"] == "bco-live-intelligence-v18"
    assert payload["webapp"] == {
        "live_stream": False,
        "cinematic_ui": True,
        "v18_overlay": False,
        "transport": "json",
    }
    assert response.headers["cache-control"].startswith("no-store")


def test_empty_stream_request_is_rejected_without_generation(monkeypatch):
    brain = StreamingBrain()
    monkeypatch.setattr(live_router._base, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._base, "APP_SETTINGS", _settings())
    response = TestClient(_app()).post("/webapp/api/ask/stream", json={"text": ""})
    assert response.status_code == 400
    event = _events(response)[0]
    assert event["error"] == "empty_text"
    assert event["request_id"]
    assert brain.calls == []
