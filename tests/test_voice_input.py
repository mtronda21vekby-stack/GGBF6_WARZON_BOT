from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.services.voice.ingress import TelegramVoiceIngress
from app.services.voice.transcription import TranscriptionResult


class FakeTelegram:
    def __init__(self):
        self.messages: list[tuple[int, str, dict | None]] = []
        self.actions: list[tuple[int, str]] = []
        self.downloads: list[tuple[str, str, int]] = []
        self.acks: list[tuple[str, str | None]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_chat_action(self, chat_id: int, action: str = "typing"):
        self.actions.append((chat_id, action))

    async def answer_callback_query(self, callback_id: str, text: str | None = None, **kwargs):
        self.acks.append((callback_id, text))

    async def download_file(self, file_id: str, destination: str, *, max_bytes: int, timeout_s: float):
        self.downloads.append((file_id, destination, max_bytes))
        Path(destination).write_bytes(b"OggS" + b"voice" * 20)
        return {"downloaded_bytes": Path(destination).stat().st_size}


class FakeTranscription:
    model = "gpt-4o-transcribe"

    def __init__(
        self,
        text: str = "Почему я постоянно умираю на поздней ротации в Warzone?",
        confidence: float | None = 0.94,
    ):
        self.text = text
        self.confidence = confidence
        self.paths: list[Path] = []

    async def transcribe_result(self, path, **kwargs):
        self.paths.append(Path(path))
        return TranscriptionResult(
            text=self.text,
            confidence=self.confidence,
            model=self.model,
            language="ru",
        )


class RecordingGuard:
    def __init__(self, allowed: bool = True):
        self.allowed = allowed
        self.categories: list[str] = []

    def check(self, subject, category: str):
        self.categories.append(category)
        return SimpleNamespace(allowed=self.allowed, retry_after_s=7)


def run(coro):
    return asyncio.run(coro)


def voice_update(*, duration: int = 14, size: int = 24000):
    return {
        "update_id": 77,
        "message": {
            "message_id": 8,
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 123, "username": "operator"},
            "voice": {
                "file_id": "voice-file",
                "file_unique_id": "unique",
                "duration": duration,
                "mime_type": "audio/ogg",
                "file_size": size,
            },
        },
    }


def video_note_update(*, duration: int = 11, size: int = 32000):
    return {
        "update_id": 79,
        "message": {
            "message_id": 9,
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 123, "username": "operator"},
            "video_note": {
                "file_id": "round-video-file",
                "file_unique_id": "video-unique",
                "duration": duration,
                "length": 360,
                "file_size": size,
            },
        },
    }


def confirmation_update(callback_data: str):
    return {
        "update_id": 78,
        "callback_query": {
            "id": "cb-voice",
            "from": {"id": 123, "username": "operator"},
            "message": {
                "message_id": 44,
                "chat": {"id": 123, "type": "private"},
            },
            "data": callback_data,
        },
    }


def test_high_confidence_voice_becomes_normal_text_update_for_existing_router():
    tg = FakeTelegram()
    transcription = FakeTranscription(confidence=0.96)
    ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=transcription,
        enabled=True,
        max_bytes=1024 * 1024,
        max_duration_s=300,
        confidence_threshold=0.58,
    )

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is True
    message = transformed["message"]
    assert message["text"] == "Почему я постоянно умираю на поздней ротации в Warzone?"
    assert message["_bco_input_mode"] == "voice"
    assert message["_bco_voice_duration_s"] == 14
    assert message["_bco_voice_confidence"] == 0.96
    assert message["_bco_voice_model"] == "gpt-4o-transcribe"
    assert "voice" not in message
    assert tg.actions == [(123, "typing")]
    assert tg.downloads and tg.downloads[0][0] == "voice-file"
    assert tg.messages == []


def test_video_note_audio_is_transcribed_into_same_intelligence_core():
    tg = FakeTelegram()
    transcription = FakeTranscription(text="Разбери мой последний пуш на хайграунд.", confidence=0.91)
    ingress = TelegramVoiceIngress(tg=tg, transcription=transcription, enabled=True)

    transformed, handled = run(ingress.transform(video_note_update()))

    assert handled is True
    message = transformed["message"]
    assert message["text"] == "Разбери мой последний пуш на хайграунд."
    assert message["_bco_input_mode"] == "voice"
    assert "video_note" not in message
    assert tg.downloads[0][0] == "round-video-file"
    assert transcription.paths[0].suffix == ".mp4"


def test_incoming_transcription_uses_stt_budget_not_tts_voice_budget():
    tg = FakeTelegram()
    guard = RecordingGuard()
    ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=FakeTranscription(),
        usage_guard=guard,
        enabled=True,
    )

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is True
    assert transformed["message"]["_bco_input_mode"] == "voice"
    assert guard.categories == ["stt"]


def test_stt_cooldown_consumes_media_without_calling_transcription():
    tg = FakeTelegram()
    guard = RecordingGuard(allowed=False)
    transcription = FakeTranscription()
    ingress = TelegramVoiceIngress(tg=tg, transcription=transcription, usage_guard=guard)

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is True
    assert "voice" in transformed["message"]
    assert transcription.paths == []
    assert guard.categories == ["stt"]
    assert "7 сек" in tg.messages[-1][1]


def test_low_confidence_voice_requires_confirmation_before_ai_or_memory():
    tg = FakeTelegram()
    transcription = FakeTranscription(text="Пушить сейчас или держать высоту?", confidence=0.32)
    ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=transcription,
        enabled=True,
        confidence_threshold=0.58,
    )

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is True
    assert "voice" in transformed["message"]
    assert len(tg.messages) == 1
    _, text, markup = tg.messages[0]
    assert "32%" in text
    assert "Пушить сейчас" in text
    buttons = [button for row in markup["inline_keyboard"] for button in row]
    accept = next(button for button in buttons if "USE TRANSCRIPT" in button["text"])
    assert accept["style"] == "success"
    assert accept["callback_data"].startswith("bco:voice:accept:")

    confirmed, confirmed_handled = run(ingress.transform(confirmation_update(accept["callback_data"])))
    assert confirmed_handled is True
    assert "callback_query" not in confirmed
    assert confirmed["message"]["text"] == "Пушить сейчас или держать высоту?"
    assert confirmed["message"]["_bco_input_mode"] == "voice_confirmed"
    assert tg.acks[-1][0] == "cb-voice"


def test_low_confidence_retry_discards_pending_transcript():
    tg = FakeTelegram()
    transcription = FakeTranscription(text="неуверенный текст", confidence=0.20)
    ingress = TelegramVoiceIngress(tg=tg, transcription=transcription, confidence_threshold=0.58)

    run(ingress.transform(voice_update()))
    _, _, markup = tg.messages[0]
    retry = next(button for row in markup["inline_keyboard"] for button in row if "RETRY" in button["text"])
    transformed, handled = run(ingress.transform(confirmation_update(retry["callback_data"])))

    assert handled is True
    assert "callback_query" in transformed
    assert "Повтори голосовое" in tg.messages[-1][1]


def test_unknown_confidence_fails_open_to_existing_router():
    tg = FakeTelegram()
    transcription = FakeTranscription(confidence=None)
    ingress = TelegramVoiceIngress(tg=tg, transcription=transcription, confidence_threshold=0.58)

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is True
    assert transformed["message"]["_bco_input_mode"] == "voice"
    assert transformed["message"]["_bco_voice_confidence"] is None


def test_voice_note_over_duration_limit_is_consumed_without_ai_call():
    tg = FakeTelegram()
    transcription = FakeTranscription()
    ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=transcription,
        enabled=True,
        max_bytes=1024 * 1024,
        max_duration_s=60,
    )

    transformed, handled = run(ingress.transform(voice_update(duration=61)))

    assert handled is True
    assert "voice" in transformed["message"]
    assert transcription.paths == []
    assert "раздели" in tg.messages[-1][1].lower()


def test_non_voice_message_passes_through_untouched():
    tg = FakeTelegram()
    transcription = FakeTranscription()
    ingress = TelegramVoiceIngress(tg=tg, transcription=transcription, enabled=True)
    source = {"message": {"chat": {"id": 123}, "text": "Привет"}}

    transformed, handled = run(ingress.transform(source))

    assert handled is False
    assert transformed == source
    assert transcription.paths == []


def test_disabled_voice_input_is_reversible():
    tg = FakeTelegram()
    transcription = FakeTranscription()
    ingress = TelegramVoiceIngress(tg=tg, transcription=transcription, enabled=False)

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is False
    assert "voice" in transformed["message"]
    assert transcription.paths == []
