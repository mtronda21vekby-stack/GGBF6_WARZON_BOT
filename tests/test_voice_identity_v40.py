from __future__ import annotations

import asyncio

from app.services.voice.openai_backend import OpenAITTSBackend, normalize_voice_identity, voice_instructions
from app.services.voice.telegram import VoiceTelegramController


class FakeTG:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))


class FakeProfiles:
    def __init__(self):
        self.data = {7: {"tts_mode": "OFF", "voice": "TEAMMATE"}}

    def get(self, chat_id):
        return dict(self.data.get(chat_id, {}))

    def patch(self, chat_id, patch):
        self.data.setdefault(chat_id, {}).update(dict(patch))


class FakeStore:
    def get(self, _chat_id):
        return []


class FakeVoice:
    enabled = True
    follow_input_active = True

    def describe(self, profile=None):
        p = profile or {}
        return {
            "provider": "OPENAI NATURAL VOICE",
            "voice": str(p.get("tts_voice") or "marin").upper(),
            "local_fallback": True,
            "mastering": "NATURAL MASTER V3",
        }


def test_voice_identity_normalization_and_default_timbres():
    assert normalize_voice_identity("FEMALE") == "female"
    assert normalize_voice_identity("male") == "male"
    assert normalize_voice_identity("unknown") == ""

    backend = OpenAITTSBackend(api_key="test", default_voice="marin")
    try:
        assert backend.voice_for({"voice_identity": "female"}) == "marin"
        assert backend.voice_for({"voice_identity": "male"}) == "cedar"
        assert backend.voice_for({"voice_identity": "male", "tts_voice": "coral"}) == "coral"
    finally:
        asyncio.run(backend.close())


def test_voice_identity_direction_rejects_theatrical_delivery():
    female = voice_instructions({"voice_identity": "female", "voice": "TEAMMATE"}, "Пушим после UAV.")
    male = voice_instructions({"voice_identity": "male", "voice": "COACH"}, "Разбери мой файт.")
    assert "female tactical-intelligence" in female
    assert "never childish" in female
    assert "male tactical-intelligence" in male
    assert "no trailer voice" in male
    assert "Do not add filler sounds" in female


def test_telegram_identity_buttons_persist_identity_and_default_timbre():
    tg = FakeTG()
    profiles = FakeProfiles()
    controller = VoiceTelegramController(tg=tg, profiles=profiles, store=FakeStore(), voice=FakeVoice())

    handled = asyncio.run(controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "♀ CROWN // FEMALE"}}))
    assert handled is True
    assert profiles.get(7)["voice_identity"] == "female"
    assert profiles.get(7)["tts_voice"] == "marin"
    assert "CROWN // FEMALE" in tg.messages[-1][1]

    handled = asyncio.run(controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "♂ CROWN // MALE"}}))
    assert handled is True
    assert profiles.get(7)["voice_identity"] == "male"
    assert profiles.get(7)["tts_voice"] == "cedar"
    assert "CROWN // MALE" in tg.messages[-1][1]
