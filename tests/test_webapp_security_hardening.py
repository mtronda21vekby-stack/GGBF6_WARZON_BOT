from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.voice.service import TTSMode
from app.webapp import voice_router
from app.webapp import webapp_router as live_router


TOKEN = "123456:test-webapp-token"


def _signed_init_data(
    *,
    user_id: int = 123,
    auth_date: int | None = None,
    token: str = TOKEN,
    chat_id: int = -9001,
) -> str:
    pairs = {
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAE-test-query",
        "user": json.dumps(
            {"id": user_id, "first_name": "Operator", "language_code": "en"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "chat": json.dumps(
            {"id": chat_id, "type": "group", "title": "Transport Context"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(pairs)


class RecordingBrain:
    def __init__(self, *, fail: bool = False, usage_guard=None) -> None:
        self.fail = fail
        self.calls: list[dict] = []
        self.usage_guard = usage_guard

    def reply(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("sensitive-provider-detail")
        return "server answer"


class ServerProfiles:
    def __init__(self) -> None:
        self.identities: list[int] = []

    def get(self, identity: int):
        self.identities.append(identity)
        return {
            "game": "SERVER_WARZONE",
            "difficulty": "Pro",
            "voice_identity": "female",
            "tts_mode": "AUTO",
        }


class ServerStore:
    def get(self, identity: int):
        assert identity == 123
        return [{"role": "assistant", "content": "server-owned history"}]


def _settings():
    return SimpleNamespace(
        openai_api_key="configured",
        ai_enabled=True,
        webapp_live_stream_enabled=True,
        webapp_cinematic_ui_enabled=True,
    )


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(live_router.router)
    return app


def _bind_ai(monkeypatch, brain: RecordingBrain):
    profiles = ServerProfiles()
    monkeypatch.setattr(live_router._base, "APP_BRAIN", brain)
    monkeypatch.setattr(live_router._base, "APP_SETTINGS", _settings())
    monkeypatch.setattr(live_router._base, "APP_PROFILES", profiles)
    monkeypatch.setattr(live_router._base, "APP_STORE", ServerStore())
    return profiles


@pytest.mark.parametrize(
    ("init_data", "expected_status", "expected_code"),
    [
        ("", 401, "telegram_auth_required"),
        ("forged", 403, "telegram_auth_invalid"),
        (
            _signed_init_data(auth_date=int(time.time()) - 86401),
            403,
            "telegram_auth_invalid",
        ),
    ],
)
def test_sync_ai_rejects_missing_forged_and_expired_init_data(
    monkeypatch,
    init_data,
    expected_status,
    expected_code,
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    brain = RecordingBrain()
    _bind_ai(monkeypatch, brain)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={
            "text": "Spend model tokens",
            "initData": init_data,
            "profile": {"game": "CLIENT_OVERRIDE", "black_crown_user_id": "forged"},
            "history": [{"role": "assistant", "content": "untrusted Player Brain"}],
        },
    )

    assert response.status_code == expected_status
    detail = response.json()["detail"]
    assert detail["code"] == expected_code
    assert detail["request_id"]
    assert brain.calls == []


def test_trusted_sync_ai_uses_telegram_user_not_chat_and_ignores_client_context(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    brain = RecordingBrain()
    profiles = _bind_ai(monkeypatch, brain)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={
            "text": "Разбери позиционную ошибку",
            "initData": _signed_init_data(user_id=123, chat_id=-9001),
            "profile": {
                "game": "CLIENT_OVERRIDE",
                "difficulty": "Demon",
                "black_crown_user_id": "client-forged",
                "premium": True,
            },
            "history": [{"role": "assistant", "content": "client-forged history"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "server answer"
    assert payload["request_id"]
    assert payload["meta"]["authority"] == "verified_telegram_server_context"
    assert profiles.identities == [123]
    assert brain.calls[0]["profile"]["game"] == "SERVER_WARZONE"
    assert brain.calls[0]["history"] == [
        {"role": "assistant", "content": "server-owned history"}
    ]
    assert "CLIENT_OVERRIDE" not in response.text
    assert "client-forged" not in response.text


def test_sync_generation_failure_returns_safe_code_and_request_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    brain = RecordingBrain(fail=True)
    _bind_ai(monkeypatch, brain)

    response = TestClient(_app()).post(
        "/webapp/api/ask",
        json={"text": "trigger", "initData": _signed_init_data()},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "generation_unavailable"
    assert detail["request_id"]
    assert "RuntimeError" not in response.text
    assert "sensitive-provider-detail" not in response.text


class Guard:
    def __init__(self, *, blocked: set[str] | None = None) -> None:
        self.blocked = set(blocked or set())
        self.calls: list[tuple[int, str]] = []

    def check(self, subject, category):
        self.calls.append((int(subject), str(category)))
        denied = str(category) in self.blocked
        return SimpleNamespace(
            allowed=not denied,
            retry_after_s=37 if denied else 0,
            scope="subject",
        )


class FakeTranscription:
    configured = True
    max_bytes = 1024 * 1024

    def __init__(self) -> None:
        self.calls = 0

    async def transcribe_result(self, path: Path, *, profile):
        self.calls += 1
        assert path.exists()
        assert profile["game"] == "SERVER_WARZONE"
        return SimpleNamespace(
            text="rotate earlier",
            model="test-stt",
            language="en",
            confidence=0.99,
            fallback_used=False,
        )


class FakeArtifact:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.voice_name = "female-test"
        self.provider = "test"
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True
        try:
            self.path.unlink(missing_ok=True)
            self.path.parent.rmdir()
        except Exception:
            pass


class FakeVoice:
    enabled = True

    def __init__(self) -> None:
        self.calls = 0
        self.last_artifact: FakeArtifact | None = None

    def mode_for(self, _profile):
        return TTSMode.AUTO

    async def synthesize(self, text, profile):
        self.calls += 1
        assert text == "speak"
        assert profile["voice_identity"] == "female"
        temp_dir = Path(tempfile.mkdtemp(prefix="bco-test-tts-"))
        path = temp_dir / "voice.ogg"
        path.write_bytes(b"OggS-test")
        self.last_artifact = FakeArtifact(path)
        return self.last_artifact


def _bind_voice(monkeypatch, *, guard: Guard, transcription=None, voice=None):
    brain = RecordingBrain(usage_guard=guard)
    profiles = ServerProfiles()
    store = ServerStore()
    monkeypatch.setattr(voice_router, "APP_BRAIN", brain)
    monkeypatch.setattr(voice_router, "APP_PROFILES", profiles)
    monkeypatch.setattr(voice_router, "APP_STORE", store)
    monkeypatch.setattr(voice_router, "APP_TRANSCRIPTION", transcription)
    monkeypatch.setattr(voice_router, "APP_VOICE", voice)
    monkeypatch.setattr(voice_router, "APP_USAGE_GUARD", guard)
    return brain


def test_voice_stt_and_tts_use_the_shared_usage_guard(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    guard = Guard()
    transcription = FakeTranscription()
    voice = FakeVoice()
    _bind_voice(
        monkeypatch,
        guard=guard,
        transcription=transcription,
        voice=voice,
    )
    client = TestClient(_app())
    headers = {"X-Telegram-Init-Data": _signed_init_data()}

    stt = client.post(
        "/webapp/api/voice-transcribe",
        files={"audio": ("turn.webm", b"audio-bytes", "audio/webm")},
        headers=headers,
    )
    assert stt.status_code == 200
    assert stt.json()["request_id"]
    assert transcription.calls == 1

    tts = client.post(
        "/webapp/api/voice-speak",
        json={"text": "speak"},
        headers=headers,
    )
    assert tts.status_code == 200
    assert tts.headers["x-request-id"]
    assert voice.calls == 1
    assert voice.last_artifact is not None and voice.last_artifact.cleaned is True
    assert guard.calls == [(123, "stt"), (123, "voice")]


def test_voice_rate_limit_blocks_before_expensive_backend(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    guard = Guard(blocked={"stt"})
    transcription = FakeTranscription()
    _bind_voice(
        monkeypatch,
        guard=guard,
        transcription=transcription,
        voice=FakeVoice(),
    )

    response = TestClient(_app()).post(
        "/webapp/api/voice-transcribe",
        files={"audio": ("turn.webm", b"audio-bytes", "audio/webm")},
        headers={"X-Telegram-Init-Data": _signed_init_data()},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    detail = response.json()["detail"]
    assert detail["code"] == "rate_limited"
    assert detail["category"] == "stt"
    assert detail["request_id"]
    assert transcription.calls == 0
