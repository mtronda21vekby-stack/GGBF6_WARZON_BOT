from __future__ import annotations

import asyncio

from app.services.entitlements.service import EntitlementStatus, LinkChallenge
from app.services.entitlements.telegram import EntitlementTelegramController


class FakeTelegram:
    def __init__(self):
        self.messages: list[tuple[int, str, dict | None]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        self.messages.append((chat_id, text, reply_markup))


class FakeService:
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
            expires_at="2026-08-16T20:00:00Z",
            ttl_seconds=600,
        )

    async def unlink(self, user_id: int):
        self.unlinked.append(user_id)
        self.status = EntitlementStatus()
        return True


def update(text: str, *, chat_type: str = "private", user_id: int = 123, chat_id: int | None = None):
    return {
        "message": {
            "chat": {"id": chat_id if chat_id is not None else user_id, "type": chat_type},
            "from": {"id": user_id, "username": "Test_User"},
            "text": text,
        }
    }


def run(coro):
    return asyncio.run(coro)


def test_premium_hub_shows_authoritative_server_status():
    tg = FakeTelegram()
    service = FakeService()
    service.status = EntitlementStatus(
        linked=True,
        premium=True,
        entitlements=("bco_premium",),
    )
    controller = EntitlementTelegramController(tg=tg, service=service)

    assert run(controller.maybe_handle_command(update("💎 Premium"))) is True
    _, text, keyboard = tg.messages[-1]
    assert "Premium: ACTIVE" in text
    assert "bco_premium" in text
    assert keyboard and keyboard["keyboard"][0][0]["text"] == "🔗 Связать с сайтом"


def test_link_uses_telegram_from_id_and_sends_fragment_url_button():
    tg = FakeTelegram()
    service = FakeService()
    controller = EntitlementTelegramController(tg=tg, service=service)

    assert run(controller.maybe_handle_command(update("🔗 Связать с сайтом", user_id=8275036156))) is True
    assert service.created == [
        {
            "telegram_user_id": 8275036156,
            "telegram_chat_id": 8275036156,
            "telegram_username": "Test_User",
        }
    ]
    _, text, markup = tg.messages[-1]
    assert "НЕ выдаёт Premium" in text
    url = markup["inline_keyboard"][0][0]["url"]
    assert url.startswith("https://blackcrown.work/account/telegram#telegram-link=")
    assert "?telegram-link=" not in url


def test_link_is_refused_outside_private_chat():
    tg = FakeTelegram()
    service = FakeService()
    controller = EntitlementTelegramController(tg=tg, service=service)

    assert run(
        controller.maybe_handle_command(
            update("🔗 Связать с сайтом", chat_type="group", user_id=123, chat_id=-100500)
        )
    ) is True
    assert service.created == []
    assert "только в личном чате" in tg.messages[-1][1]


def test_unlink_requires_explicit_confirmation():
    tg = FakeTelegram()
    service = FakeService()
    service.status = EntitlementStatus(linked=True, premium=True, entitlements=("bco_premium",))
    controller = EntitlementTelegramController(tg=tg, service=service)

    assert run(controller.maybe_handle_command(update("🔓 Отвязать сайт"))) is True
    assert service.unlinked == []
    assert "Подтверди отвязку" in tg.messages[-1][1]

    assert run(controller.maybe_handle_command(update("⚠️ Подтвердить отвязку"))) is True
    assert service.unlinked == [123]
    assert "Аккаунты отвязаны" in tg.messages[-1][1]


def test_unrelated_message_passes_to_existing_router():
    controller = EntitlementTelegramController(tg=FakeTelegram(), service=FakeService())
    assert run(controller.maybe_handle_command(update("Почему я умер на ротации?"))) is False
