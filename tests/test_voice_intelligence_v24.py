from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.voice.ingress import TelegramVoiceIngress
from app.services.voice.transcription import TranscriptionResult, build_transcription_prompt


class FakeTG:
    def __init__(self):
        self.messages = []
        self.actions = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_chat_action(self, chat_id, action):
        self.actions.append((chat_id, action))

    async def download_file(self, file_id, destination, **kwargs):
        Path(destination).write_bytes(b"OggS" + b"x" * 128)
        return {"downloaded_bytes": 132}


class FakeProfiles:
    def get(self, chat_id):
        return {
            "game": "Warzone",
            "mode": "Resurgence",
            "role": "Entry",
            "platform": "Xbox",
            "input": "Controller",
            "preferred_weapons": ["KSV", "CR-56 AMAX"],
        }


class FakeSTT:
    model = "gpt-4o-transcribe"

    def __init__(self, result):
        self.result = result
        self.profile = None

    async def transcribe_result(self, path, *, profile=None):
        self.profile = dict(profile or {})
        return self.result


def run(coro):
    return asyncio.run(coro)


def voice_update():
    return {
        "message": {
            "message_id": 7,
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 123},
            "voice": {"file_id": "VOICE", "duration": 12, "file_size": 1200, "mime_type": "audio/ogg"},
        }
    }


def test_transcription_prompt_contains_player_game_vocabulary():
    prompt = build_transcription_prompt(FakeProfiles().get(123))
    assert "Warzone" in prompt
    assert "Resurgence" in prompt
    assert "Entry" in prompt
    assert "Xbox" in prompt
    assert "Controller" in prompt
    assert "KSV" in prompt
    assert "CR-56 AMAX" in prompt


def test_high_confidence_voice_becomes_text_for_same_intelligence_core():
    tg = FakeTG()
    stt = FakeSTT(
        TranscriptionResult(
            text="Почему я постоянно умираю на ротации в Resurgence?",
            confidence=0.91,
            model="gpt-4o-transcribe",
            language="ru",
        )
    )
    ingress = TelegramVoiceIngress(tg=tg, transcription=stt, profiles=FakeProfiles())

    transformed, handled = run(ingress.transform(voice_update()))
    assert handled is True
    assert transformed["message"]["text"].startswith("Почему я")
    assert transformed["message"]["_bco_input_mode"] == "voice"
    assert transformed["message"]["_bco_voice_confidence"] == 0.91
    assert stt.profile["game"] == "Warzone"
    assert tg.messages == []


def test_low_confidence_voice_is_not_sent_to_memory_before_confirmation():
    tg = FakeTG()
    stt = FakeSTT(
        TranscriptionResult(
            text="Похоже я сказал про ротацию",
            confidence=0.31,
            model="gpt-4o-transcribe",
            language="ru",
        )
    )
    ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=stt,
        profiles=FakeProfiles(),
        confidence_threshold=0.58,
    )

    transformed, handled = run(ingress.transform(voice_update()))
    assert handled is True
    assert "voice" in transformed["message"]
    assert len(tg.messages) == 1
    _, text, markup = tg.messages[0]
    assert "31%" in text
    labels = [button["text"] for row in markup["inline_keyboard"] for button in row]
    assert labels == ["✓ USE TRANSCRIPT", "↻ RETRY"]
    assert len(ingress.pending) == 1
