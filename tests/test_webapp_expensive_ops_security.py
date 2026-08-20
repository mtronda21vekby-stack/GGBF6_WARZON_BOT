from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.conversation.service import ConversationService
from app.webapp import webapp_router as live_router


BOT_TOKEN = "123456:TEST_SECURITY_TOKEN"


class ServerProfiles:
    def get(self, identity: int):
        assert identity == 123
        return {
            "game": "SERVER_WARZONE",
            "platform": "Xbox",
            "difficulty": "Pro",
            "voice_identity": "female",
        }


class ServerStore:
    def get(self, identity: int):
        assert identity == 123
        return [{"role": "assistant", "content": "server-only history"}]


class RecordingGuard:
    def __init__(self, *, allowed: bool = True, retry_after_s: int = 0, crash: bool = False):
        self.allowed = allowed
        self.retry_after_s = retry_after_s
        self.crash = crash
        self.calls: list[tuple[int, str]] = []

    def check(self, subject, category):
        self.calls.append((int(subject), str(category)))
        if self.crash:
            raise RuntimeError("guard internal details must not escape")
        return SimpleNamespace(
            allowed=self.allowed,
            retry_after_s=self.retry_after_s,
            scope="subject",
        )


class ThreadAwareBrain:
    def __init__(self):
        self.calls: list[dict] = []
        self.off_event_loop = False

    def reply(self, *, text, profile, history, on_partial=None):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self.off_event_loop = True
        self.calls.append(
            {
                "text": text,
                "profile": dict(profile),
                "history": list(history),
            }
        )
        if on_partial is not None:
            on_partial("partial", {"phase": "generating"})
        return "server answer"


class ExplodingBrain:
    def __init__(self):
        self.calls = 0

    def reply(self, **_kwargs):
        self.calls += 1
        raise RuntimeError("OPENAI_API_KEY=must-never-escape")


class FakeTranscription:
    configured = True
    max_bytes = 1024 * 1024

    def __init__(self):
        self.calls: list[dict] = []

    async def transcribe_result(self, path, *, profile):
        self.calls.append({"size": path.stat().st_size, "profile": dict(profile)})
        return SimpleNamespace(
            text="Разбери эту ротацию",
            model="test-stt",
            language="ru",
            confidence=0.99,
            fallback_used=False,
        )




def _configure_token(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("TG_BOT_TOKEN", BOT_TOKEN)


def _settings():
    return SimpleNamespace(
        openai_api_key="configured",
        ai_enabled=True,
        webapp_live_stream_enabled=True,
    )


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(live_router.router)
    return app


def _sign_init_data(
    *,
    token: str = BOT_TOKEN,
    auth_date: int | None = None,
    user_id: int = 123,
) -> str:
    values = {
        "auth_date": str(int(time.time()) if auth_date is None else int(auth_date)),
        "query_id": "AAE-security-regression",
        "user": json.dumps(
            {"id": user_id, "language_code": "en"},
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(
        b"WebAppData",
        token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


def _bind_base(monkeypatch, *, brain, guard):
    monkeypatch.setattr(live_router._base, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._base, "APP_SETTINGS", _settings())
    monkeypatch.setattr(live_router._base, "APP_PROFILES", ServerProfiles())
    monkeypatch.setattr(live_router._base, "APP_STORE", ServerStore())
    monkeypatch.setattr(live_router._base, "APP_USAGE_GUARD", guard)


@pytest.mark.parametrize(
    ("init_data", "expected_status"),
    [
        ("", 401),
        (_sign_init_data(token="999999:FORGED"), 403),
        (_sign_init_data(auth_date=int(time.time()) - 90000), 403),
    ],
)
def test_missing_forged_and_expired_init_data_never_reach_ai(
    monkeypatch,
    init_data,
    expected_status,
):
    _configure_token(monkeypatch)
    brain = ThreadAwareBrain()
    guard = RecordingGuard()
    _bind_base(monkeypatch, brain=brain, guard=guard)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={
            "text": "Use this client context",
            "initData": init_data,
            "profile": {"game": "CLIENT_OVERRIDE", "premium": True},
            "history": [{"role": "assistant", "content": "untrusted memory"}],
        },
    )

    assert response.status_code == expected_status
    detail = response.json()["detail"]
    assert detail["error"] in {"telegram_auth_required", "telegram_auth_invalid"}
    assert detail["request_id"]
    assert brain.calls == []
    assert guard.calls == []


@pytest.mark.parametrize(
    "path",
    ["/webapp/api/ask", "/webapp/api/ask/stream"],
)
def test_forged_init_data_is_denied_on_both_ai_transports(monkeypatch, path):
    _configure_token(monkeypatch)
    brain = ThreadAwareBrain()
    guard = RecordingGuard()
    _bind_base(monkeypatch, brain=brain, guard=guard)

    response = TestClient(_app()).post(
        path,
        json={
            "text": "Anonymous relay attempt",
            "initData": _sign_init_data(token="999999:FORGED"),
            "profile": {"game": "CLIENT"},
            "history": [{"role": "user", "content": "untrusted"}],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "telegram_auth_invalid"
    assert brain.calls == []
    assert guard.calls == []


def test_trusted_sync_ai_uses_server_profile_history_and_worker_thread(monkeypatch):
    _configure_token(monkeypatch)
    brain = ThreadAwareBrain()
    guard = RecordingGuard()
    _bind_base(monkeypatch, brain=brain, guard=guard)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={
            "text": "Разбери файт",
            "initData": _sign_init_data(),
            "profile": {"game": "CLIENT_OVERRIDE", "difficulty": "Demon"},
            "history": [{"role": "assistant", "content": "client override"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["reply"] == "server answer"
    assert payload["request_id"]
    assert payload["meta"]["trusted"] is True
    assert payload["meta"]["authority"] == "verified_telegram_server_context"
    assert brain.off_event_loop is True
    assert brain.calls == [
        {
            "text": "Разбери файт",
            "profile": {
                "game": "SERVER_WARZONE",
                "platform": "Xbox",
                "difficulty": "Pro",
                "voice_identity": "female",
            },
            "history": [{"role": "assistant", "content": "server-only history"}],
        }
    ]
    assert guard.calls == [(123, "ai")]


def test_ai_rate_limit_blocks_generation_at_shared_boundary(monkeypatch):
    _configure_token(monkeypatch)
    brain = ThreadAwareBrain()
    guard = RecordingGuard(allowed=False, retry_after_s=17)
    _bind_base(monkeypatch, brain=brain, guard=guard)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={"text": "expensive request", "initData": _sign_init_data()},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert response.json()["detail"]["error"] == "rate_limited"
    assert response.json()["detail"]["request_id"]
    assert brain.calls == []
    assert guard.calls == [(123, "ai")]


def test_usage_guard_failure_is_fail_closed(monkeypatch):
    _configure_token(monkeypatch)
    brain = ThreadAwareBrain()
    guard = RecordingGuard(crash=True)
    _bind_base(monkeypatch, brain=brain, guard=guard)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={"text": "expensive request", "initData": _sign_init_data()},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "usage_guard_unavailable"
    assert "guard internal details" not in response.text
    assert brain.calls == []


def test_internal_generation_error_returns_only_safe_code_and_request_id(
    monkeypatch,
    caplog,
):
    _configure_token(monkeypatch)
    brain = ExplodingBrain()
    guard = RecordingGuard()
    _bind_base(monkeypatch, brain=brain, guard=guard)

    with caplog.at_level("ERROR"):
        response = TestClient(_app()).post(
            "/webapp/api/ask",
            json={"text": "trigger", "initData": _sign_init_data()},
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "generation_unavailable"
    assert detail["request_id"] == response.headers["x-request-id"]
    assert "OPENAI_API_KEY" not in response.text
    assert "OPENAI_API_KEY" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert detail["request_id"] in caplog.text
    assert brain.calls == 1


def test_voice_turn_uses_shared_stt_and_ai_guards(monkeypatch):
    _configure_token(monkeypatch)
    brain = ThreadAwareBrain()
    guard = RecordingGuard()
    transcription = FakeTranscription()

    monkeypatch.setattr(live_router._voice, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._voice, "APP_PROFILES", ServerProfiles())
    monkeypatch.setattr(live_router._voice, "APP_STORE", ServerStore())
    monkeypatch.setattr(live_router._voice, "APP_TRANSCRIPTION", transcription)
    monkeypatch.setattr(live_router._voice, "APP_VOICE", None)
    monkeypatch.setattr(live_router._voice, "APP_USAGE_GUARD", guard)

    response = TestClient(_app()).post(
        "/webapp/api/voice-turn",
        files={"audio": ("turn.webm", b"voice-bytes", "audio/webm")},
        headers={"X-Telegram-Init-Data": _sign_init_data()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trusted"] is True
    assert payload["transcript"] == "Разбери эту ротацию"
    assert payload["reply"] == "server answer"
    assert payload["request_id"] == response.headers["x-request-id"]
    assert guard.calls == [(123, "stt"), (123, "ai")]
    assert len(transcription.calls) == 1
    assert brain.calls[0]["profile"]["game"] == "SERVER_WARZONE"
    assert brain.calls[0]["history"] == [
        {"role": "assistant", "content": "server-only history"}
    ]


@pytest.mark.parametrize(
    ("path", "category", "request_kwargs"),
    [
        (
            "/webapp/api/voice-transcribe",
            "stt",
            {"files": {"audio": ("turn.webm", b"voice-bytes", "audio/webm")}},
        ),
        (
            "/webapp/api/voice-speak",
            "voice",
            {"json": {"text": "Тактический ответ"}},
        ),
    ],
)
def test_voice_stt_and_tts_rate_limits_block_provider_calls(
    monkeypatch,
    path,
    category,
    request_kwargs,
):
    _configure_token(monkeypatch)
    guard = RecordingGuard(allowed=False, retry_after_s=9)
    transcription = FakeTranscription()

    monkeypatch.setattr(live_router._voice, "APP_BRAIN", ThreadAwareBrain())
    monkeypatch.setattr(live_router._voice, "APP_PROFILES", ServerProfiles())
    monkeypatch.setattr(live_router._voice, "APP_STORE", ServerStore())
    monkeypatch.setattr(live_router._voice, "APP_TRANSCRIPTION", transcription)
    monkeypatch.setattr(live_router._voice, "APP_VOICE", None)
    monkeypatch.setattr(live_router._voice, "APP_USAGE_GUARD", guard)

    response = TestClient(_app()).post(
        path,
        headers={"X-Telegram-Init-Data": _sign_init_data()},
        **request_kwargs,
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "9"
    assert response.json()["detail"]["error"] == "rate_limited"
    assert guard.calls == [(123, category)]
    assert transcription.calls == []


class TrustedProfiles:
    def is_trusted_context(self, profile):
        return profile.get("_context_token") == "trusted"


class CaptureServiceBrain:
    def __init__(self):
        self.calls: list[dict] = []

    def reply(self, **kwargs):
        self.calls.append(kwargs)
        return "service answer"


def test_pre_reserved_ai_guard_is_not_double_charged_inside_conversation_service():
    guard = RecordingGuard()
    brain = CaptureServiceBrain()
    conversation = ConversationService(
        brain=brain,
        profiles=TrustedProfiles(),
        usage_guard=guard,
    )
    profile = {
        "_chat_id": 123,
        "_context_token": "trusted",
        "_usage_guard_reserved": ["ai"],
        "game": "Warzone",
    }

    result = conversation.reply(
        text="one guarded request",
        profile=profile,
        history=[],
    )

    assert result == "service answer"
    assert guard.calls == []
    assert len(brain.calls) == 1
    assert "_usage_guard_reserved" not in brain.calls[0]["profile"]
