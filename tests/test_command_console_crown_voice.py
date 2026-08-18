from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.telegram.command_console import CommandConsoleController


class FakeTelegram:
    def __init__(self):
        self.sent = []
        self.edited = []
        self.answered = []
        self.removed = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))

    async def edit_message(self, chat_id, message_id, text, reply_markup=None):
        self.edited.append((chat_id, message_id, text, reply_markup))

    async def answer_callback_query(self, callback_id, text=None, *, show_alert=False, cache_time=0):
        self.answered.append((callback_id, text, show_alert))

    async def remove_reply_keyboard(self, chat_id):
        self.removed.append(chat_id)

    async def delete_message(self, chat_id, message_id):
        return None


class FakeProfiles:
    def __init__(self):
        self.data = {
            "game": "Warzone",
            "platform": "PC",
            "input": "Controller",
            "difficulty": "Demon",
            "voice": "TEAMMATE",
            "voice_identity": "female",
            "tts_voice": "marin",
            "tts_mode": "auto",
        }
        self.patches = []

    def get(self, chat_id):
        return dict(self.data)

    def patch(self, chat_id, patch):
        self.patches.append((chat_id, dict(patch)))
        self.data.update(patch)


class FakeStore:
    def stats(self, chat_id):
        return {"backend": "supabase"}


class FakeEntitlements:
    configured = False

    async def get_status(self, user_id):
        return None


def run(coro):
    return asyncio.run(coro)


def callback(data: str):
    return {
        "callback_query": {
            "id": "voice-cb",
            "from": {"id": 123, "username": "operator"},
            "message": {"message_id": 77, "chat": {"id": 123, "type": "private"}},
            "data": data,
        }
    }


def build():
    tg = FakeTelegram()
    profiles = FakeProfiles()
    controller = CommandConsoleController(
        tg=tg,
        profiles=profiles,
        store=FakeStore(),
        entitlements=FakeEntitlements(),
        settings=SimpleNamespace(telegram_aaa_console_enabled=True),
    )
    return controller, tg, profiles


def labels(markup):
    return [button["text"] for row in markup["inline_keyboard"] for button in row]


def test_home_exposes_voice_on_actual_inline_command_console():
    controller, tg, _ = build()
    run(controller.maybe_handle({"message": {"message_id": 1, "chat": {"id": 123, "type": "private"}, "from": {"id": 123}, "text": "/start"}}))
    _, text, markup = tg.sent[-1]
    assert "COMMAND CONSOLE" in text
    assert any("VOICE" in label for label in labels(markup))


def test_voice_screen_contains_female_male_role_and_output_controls():
    controller, tg, _ = build()
    assert run(controller.maybe_handle(callback("bco:voice"))) is True
    _, _, text, markup = tg.edited[-1]
    assert "CROWN VOICE" in text
    all_labels = labels(markup)
    assert any("FEMALE" in item for item in all_labels)
    assert any("MALE" in item for item in all_labels)
    assert any("TEAMMATE" in item for item in all_labels)
    assert any("COACH" in item for item in all_labels)
    assert any("AUTO" in item for item in all_labels)
    assert any("ON-DEMAND" in item for item in all_labels)


def test_female_and_male_callbacks_write_real_tts_profile_fields():
    controller, tg, profiles = build()
    assert run(controller.maybe_handle(callback("bco:set:voiceid:male"))) is True
    assert profiles.patches[-1] == (123, {"voice_identity": "male", "tts_voice": "cedar"})
    assert "IDENTITY — MALE" in tg.edited[-1][2]

    assert run(controller.maybe_handle(callback("bco:set:voiceid:female"))) is True
    assert profiles.patches[-1] == (123, {"voice_identity": "female", "tts_voice": "marin"})
    assert "IDENTITY — FEMALE" in tg.edited[-1][2]


def test_voice_output_mode_is_persisted_from_inline_console():
    controller, tg, profiles = build()
    assert run(controller.maybe_handle(callback("bco:set:ttsmode:on_demand"))) is True
    assert profiles.patches[-1] == (123, {"tts_mode": "on_demand"})
    assert "OUTPUT — ON-DEMAND" in tg.edited[-1][2]
