from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.entitlements.service import EntitlementStatus, LinkChallenge
from app.services.telegram.command_console import CommandConsoleController


class FakeTelegram:
    def __init__(self):
        self.sent: list[tuple[int, str, dict | None]] = []
        self.edited: list[tuple[int, int, str, dict | None]] = []
        self.answered: list[tuple[str, str | None, bool]] = []
        self.deleted: list[tuple[int, int]] = []
        self.removed: list[int] = []
        self.commands: list[dict[str, str]] = []
        self.menu_button: tuple[str, str] | None = None

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        self.sent.append((chat_id, text, reply_markup))

    async def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup: dict | None = None):
        self.edited.append((chat_id, message_id, text, reply_markup))

    async def answer_callback_query(self, callback_id: str, text: str | None = None, *, show_alert: bool = False, cache_time: int = 0):
        self.answered.append((callback_id, text, show_alert))

    async def delete_message(self, chat_id: int, message_id: int):
        self.deleted.append((chat_id, message_id))

    async def remove_reply_keyboard(self, chat_id: int):
        self.removed.append(chat_id)

    async def set_my_commands(self, commands: list[dict[str, str]]):
        self.commands = list(commands)

    async def set_default_menu_button(self, text: str, url: str):
        self.menu_button = (text, url)


class FakeProfiles:
    def __init__(self):
        self.data = {
            "game": "Warzone",
            "platform": "Xbox",
            "input": "Controller",
            "difficulty": "Pro",
            "voice": "TEAMMATE",
            "role": "Entry",
            "zombies_map": "Ashes",
        }
        self.patches: list[tuple[int, dict]] = []

    def get(self, chat_id: int):
        return dict(self.data)

    def patch(self, chat_id: int, patch: dict):
        self.patches.append((chat_id, dict(patch)))
        self.data.update(patch)


class FakeStore:
    def stats(self, chat_id: int):
        return {
            "backend": "supabase",
            "turns": 12,
            "recurring_mistakes": 3,
            "training_sessions": 4,
        }


class FakeEntitlements:
    configured = True

    def __init__(self):
        self.status = EntitlementStatus()
        self.created: list[dict] = []
        self.unlinked: list[int] = []

    async def get_status(self, user_id: int):
        return self.status

    async def create_link_challenge(self, **kwargs):
        self.created.append(kwargs)
        return LinkChallenge(
            code="A" * 32,
            url="https://blackcrown.work/account/telegram#telegram-link=" + "A" * 32,
            expires_at="2026-08-16T22:00:00Z",
            ttl_seconds=600,
        )

    async def unlink(self, user_id: int):
        self.unlinked.append(user_id)
        self.status = EntitlementStatus()
        return True


def run(coro):
    return asyncio.run(coro)


def message_update(text: str, user_id: int = 123):
    return {
        "message": {
            "message_id": 5,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "username": "operator"},
            "text": text,
        }
    }


def callback_update(data: str, *, user_id: int = 123, chat_id: int | None = None, chat_type: str = "private"):
    return {
        "callback_query": {
            "id": "cb-1",
            "from": {"id": user_id, "username": "operator"},
            "message": {
                "message_id": 77,
                "chat": {"id": chat_id if chat_id is not None else user_id, "type": chat_type},
            },
            "data": data,
        }
    }


def controller(tg: FakeTelegram | None = None):
    telegram = tg or FakeTelegram()
    profiles = FakeProfiles()
    entitlements = FakeEntitlements()
    instance = CommandConsoleController(
        tg=telegram,
        profiles=profiles,
        store=FakeStore(),
        entitlements=entitlements,
        settings=SimpleNamespace(telegram_aaa_console_enabled=True),
    )
    return instance, telegram, profiles, entitlements


def test_start_removes_old_keyboard_and_opens_contextual_aaa_console():
    console, tg, _, _ = controller()

    assert run(console.maybe_handle(message_update("/start"))) is True
    assert tg.removed == [123]
    assert len(tg.sent) == 1
    _, text, markup = tg.sent[0]
    assert "COMMAND CONSOLE" in text
    assert "CROWN // READY" in text
    assert "PLAYER BRAIN" in text
    assert "keyboard" not in markup
    labels = [button["text"] for row in markup["inline_keyboard"] for button in row]
    assert "WAR ROOM" in labels
    assert "🧠 AI BRIEF" in labels
    assert "OPERATOR" in labels
    assert "VOICE" in labels
    assert "ALL MODULES" in labels
    assert "🎯 TRAINING" not in labels
    assert "💎 PREMIUM" not in labels
    assert "⚙️ SYSTEM" not in labels

    assert run(console.maybe_handle(callback_update("bco:modules"))) is True
    _, _, modules_text, modules_markup = tg.edited[-1]
    assert "ALL SYSTEMS" in modules_text
    module_labels = [button["text"] for row in modules_markup["inline_keyboard"] for button in row]
    for label in ("AI BRIEF", "TRAINING", "WORLD", "VOD LAB", "ZOMBIES", "OPERATOR", "PREMIUM", "SYSTEM", "VOICE"):
        assert label in module_labels


def test_callback_is_acknowledged_and_edits_the_same_console_message():
    console, tg, _, _ = controller()

    assert run(console.maybe_handle(callback_update("bco:world"))) is True
    assert tg.answered == [("cb-1", None, False)]
    assert len(tg.edited) == 1
    chat_id, message_id, text, markup = tg.edited[0]
    assert (chat_id, message_id) == (123, 77)
    assert "WORLD SELECT" in text
    assert "inline_keyboard" in markup
    assert tg.sent == []


def test_dynamic_brain_selection_patches_profile_and_keeps_active_state():
    console, tg, profiles, _ = controller()

    assert run(console.maybe_handle(callback_update("bco:set:brain:demon"))) is True
    assert profiles.patches[-1] == (123, {"difficulty": "Demon"})
    _, _, text, markup = tg.edited[-1]
    assert "INTELLIGENCE CORE" in text
    demon = next(
        button
        for row in markup["inline_keyboard"]
        for button in row
        if "DEMON" in button["text"]
    )
    assert demon["text"].startswith("✓ ")
    assert demon["style"] == "danger"


def test_premium_link_is_generated_server_side_and_rendered_as_url_button():
    console, tg, _, entitlements = controller()

    assert run(console.maybe_handle(callback_update("bco:p:link"))) is True
    assert entitlements.created == [
        {
            "telegram_user_id": 123,
            "telegram_chat_id": 123,
            "telegram_username": "operator",
        }
    ]
    _, _, text, markup = tg.edited[-1]
    assert "PREMIUM" in text
    url_button = next(
        button for row in markup["inline_keyboard"] for button in row if button.get("url")
    )
    assert url_button["url"].startswith("https://blackcrown.work/account/telegram#telegram-link=")


def test_group_callback_is_rejected_with_alert():
    console, tg, _, _ = controller()

    assert run(
        console.maybe_handle(
            callback_update("bco:home", user_id=123, chat_id=-100500, chat_type="group")
        )
    ) is True
    assert tg.answered == [
        ("cb-1", "COMMAND CONSOLE доступна в личном чате с ботом.", True)
    ]
    assert tg.edited == []


def test_close_removes_console_message():
    console, tg, _, _ = controller()

    assert run(console.maybe_handle(callback_update("bco:close"))) is True
    assert tg.deleted == [(123, 77)]


def test_startup_configures_commands_and_default_webapp_menu(monkeypatch):
    monkeypatch.setenv("WEBAPP_URL", "https://example.test/webapp")
    monkeypatch.setenv("WEBAPP_BUILD_ID", "v16")
    import app.ui.quickbar as quickbar

    quickbar._BUILD_CACHE_VALUE = None
    console, tg, _, _ = controller()

    run(console.configure_bot_surface())
    assert any(item["command"] == "menu" for item in tg.commands)
    assert tg.menu_button == ("COMMAND CENTER", "https://example.test/webapp?v=v16")
