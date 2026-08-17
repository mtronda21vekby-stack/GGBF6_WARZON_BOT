from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.services.voice.service import TTSMode, VoiceArtifact
from app.services.voice.telegram import VoiceTelegramController


class FakeTG:
    def __init__(self):
        self.messages = []
        self.voices = []
        self.actions = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_voice_file(self, chat_id, file_path, caption=None, reply_markup=None):
        self.voices.append((chat_id, file_path, caption, reply_markup))

    async def send_chat_action(self, chat_id, action="typing"):
        self.actions.append((chat_id, action))


class FakeProfiles:
    def __init__(self):
        self.data = {7: {"tts_mode": "OFF", "voice": "TEAMMATE", "tts_voice": "marin"}}

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
    follow_input_active = True

    def should_auto(self, profile, *, input_mode="text"):
        return str(profile.get("tts_mode")) == TTSMode.AUTO.value

    def describe(self, profile=None):
        return {
            "provider": "OPENAI NATURAL VOICE",
            "voice": str((profile or {}).get("tts_voice") or "marin").upper(),
            "local_fallback": True,
            "mastering": "NATURAL MASTER V3",
        }

    async def synthesize(self, text, profile=None):
        temp_dir = Path(tempfile.mkdtemp(prefix="bco-voice-test-"))
        path = temp_dir / "voice.ogg"
        path.write_bytes(b"OggSfake")
        return VoiceArtifact(
            path=path,
            spoken_text=str(text),
            temp_dir=temp_dir,
            provider="openai",
            voice_name=str((profile or {}).get("tts_voice") or "marin"),
            mastering="natural-v3",
        )


def _controller():
    tg = FakeTG()
    profiles = FakeProfiles()
    store = FakeStore()
    return VoiceTelegramController(tg=tg, profiles=profiles, store=store, voice=FakeVoice()), tg, profiles, store


def test_voice_mode_command_persists_profile_and_shows_natural_runtime():
    controller, tg, profiles, _ = _controller()
    handled = asyncio.run(controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "🔊 Voice AUTO"}}))
    assert handled is True
    assert profiles.get(7)["tts_mode"] == "AUTO"
    panel = tg.messages[-1][1]
    assert "OPENAI NATURAL VOICE" in panel
    assert "PIPER FALLBACK" in panel
    assert "NATURAL MASTER V3" in panel
    assert "Входящие голосовые: ПОНИМАЮ" in panel
    assert "синтетические AI-голоса" in panel


def test_voice_selection_persists_marin_coral_shimmer_and_cedar():
    controller, tg, profiles, _ = _controller()
    for label, expected in [
        ("🎙 MARIN · SOFT", "marin"),
        ("🎙 CORAL · WARM", "coral"),
        ("🎙 SHIMMER · LIGHT", "shimmer"),
        ("🎙 CEDAR · TACTICAL", "cedar"),
    ]:
        handled = asyncio.run(
            controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": label}})
        )
        assert handled is True
        assert profiles.get(7)["tts_voice"] == expected
        assert expected.upper() in tg.messages[-1][1]


def test_cached_v22_voice_buttons_remain_compatible():
    controller, _, profiles, _ = _controller()
    assert asyncio.run(
        controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "🎙 MARIN"}})
    ) is True
    assert profiles.get(7)["tts_voice"] == "marin"


def test_voice_preview_works_even_when_delivery_mode_is_off():
    controller, tg, profiles, _ = _controller()
    assert profiles.get(7)["tts_mode"] == "OFF"

    handled = asyncio.run(
        controller.maybe_handle_command({"message": {"chat": {"id": 7}, "text": "🧪 Тест голоса"}})
    )

    assert handled is True
    assert len(tg.voices) == 1
    assert tg.actions == [(7, "record_voice"), (7, "upload_voice")]
    assert "Синтетический AI-голос" in tg.voices[0][2]


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
    assert "Синтетический AI-голос" in tg.voices[0][2]


def test_auto_only_runs_when_history_changed():
    controller, tg, profiles, store = _controller()
    profiles.patch(7, {"tts_mode": "AUTO"})
    before = controller.history_signature(7)
    assert asyncio.run(controller.maybe_auto(7, before)) is False
    store.history[7] = [{"role": "assistant", "content": "New answer"}]
    assert asyncio.run(controller.maybe_auto(7, before)) is True
    assert len(tg.voices) == 1
