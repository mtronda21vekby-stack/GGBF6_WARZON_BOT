from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from app.services.voice.service import TTSMode, VoiceArtifact
from app.services.voice.telegram import VoiceTelegramController


class FakeTG:
    def __init__(self):
        self.messages = []
        self.voices = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_voice_file(self, chat_id, file_path, caption=None, reply_markup=None):
        self.voices.append((chat_id, file_path))


class FakeProfiles:
    def __init__(self):
        self.data = {7: {"tts_mode": "OFF", "voice": "TEAMMATE"}}

    def get(self, chat_id):
        return dict(self.data.get(chat_id, {}))

    def patch(self, chat_id, patch):
        self.data.setdefault(chat_id, {}).update(dict(patch))


class FakeStore:
    def __init__(self):
        self.history = {7: []}

    def get(self, chat_id):
        return list(self.history.get(chat_id, []))


class FakeVoice:
    enabled = True

    def should_auto(self, profile):
        return str(profile.get("tts_mode")) == TTSMode.AUTO.value

    async def synthesize(self, text, profile=None):
        temp_dir = Path(tempfile.mkdtemp(prefix="bco-voice-test-"))
        path = temp_dir / "voice.ogg"
        path.write_bytes(b"OggSfake")
        return VoiceArtifact(path=path, spoken_text=str(text), temp_dir=temp_dir)


def _controller():
    tg = FakeTG()
    profiles = FakeProfiles()
    store = FakeStore()
    return VoiceTelegramController(tg=tg, profiles=profiles, store=store, voice=FakeVoice()), tg, profiles, store


def test_voice_mode_command_persists_profile():
    controller, tg, profiles, _ = _controller()
    handled = asyncio.run(controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "🔊 Voice AUTO"}}))
    assert handled is True
    assert profiles.get(7)["tts_mode"] == "AUTO"
    assert tg.messages


def test_on_demand_sends_last_ai_reply():
    controller, tg, profiles, store = _controller()
    profiles.patch(7, {"tts_mode": "ON_DEMAND"})
    store.history[7] = [
        {"role": "user", "content": "why"},
        {"role": "assistant", "content": "Rotate earlier."},
    ]
    handled = asyncio.run(controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "🔊 Озвучить ответ"}}))
    assert handled is True
    assert len(tg.voices) == 1


def test_auto_only_runs_when_history_changed():
    controller, tg, profiles, store = _controller()
    profiles.patch(7, {"tts_mode": "AUTO"})
    before = controller.history_signature(7)
    assert asyncio.run(controller.maybe_auto(7, before)) is False
    store.history[7] = [{"role": "assistant", "content": "New answer"}]
    assert asyncio.run(controller.maybe_auto(7, before)) is True
    assert len(tg.voices) == 1
