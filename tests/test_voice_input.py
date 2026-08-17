from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.voice.ingress import TelegramVoiceIngress


class FakeTelegram:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []
        self.actions: list[tuple[int, str]] = []
        self.downloads: list[tuple[str, str, int]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None):
        self.messages.append((chat_id, text))

    async def send_chat_action(self, chat_id: int, action: str = "typing"):
        self.actions.append((chat_id, action))

    async def download_file(self, file_id: str, destination: str, *, max_bytes: int, timeout_s: float):
        self.downloads.append((file_id, destination, max_bytes))
        Path(destination).write_bytes(b"OggS" + b"voice" * 20)
        return {"downloaded_bytes": Path(destination).stat().st_size}


class FakeTranscription:
    model = "gpt-4o-mini-transcribe"

    def __init__(self, text: str = "Почему я постоянно умираю на поздней ротации в Warzone?"):
        self.text = text
        self.paths: list[Path] = []

    async def transcribe(self, path):
        self.paths.append(Path(path))
        return self.text


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


def test_voice_note_becomes_normal_text_update_for_existing_router():
    tg = FakeTelegram()
    transcription = FakeTranscription()
    ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=transcription,
        enabled=True,
        max_bytes=1024 * 1024,
        max_duration_s=300,
    )

    transformed, handled = run(ingress.transform(voice_update()))

    assert handled is True
    message = transformed["message"]
    assert message["text"] == "Почему я постоянно умираю на поздней ротации в Warzone?"
    assert message["_bco_input_mode"] == "voice"
    assert message["_bco_voice_duration_s"] == 14
    assert "voice" not in message
    assert tg.actions == [(123, "typing")]
    assert tg.downloads and tg.downloads[0][0] == "voice-file"
    assert tg.messages == []


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
