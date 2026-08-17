from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.core.router import Router


class FakeTelegram:
    def __init__(self):
        self.drafts: list[tuple[int, int, str]] = []
        self.messages: list[tuple[int, str, dict | None]] = []
        self.actions: list[tuple[int, str]] = []

    async def send_live_draft(self, chat_id: int, draft_id: int, text: str):
        self.drafts.append((chat_id, draft_id, text))
        return "rich"

    async def send_message(self, chat_id: int, text: str, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_chat_action(self, chat_id: int, action: str):
        self.actions.append((chat_id, action))


class FakeBrain:
    def __init__(self):
        self.calls: list[dict] = []

    def reply(self, *, text, profile, history, on_partial=None):
        self.calls.append({"text": text, "profile": dict(profile), "history": list(history)})
        if on_partial:
            on_partial("Причина: поздняя ротация.", {"phase": "generating", "attempt": 1})
            on_partial(
                "Причина: поздняя ротация. Коррекция: двигайся на десять секунд раньше.",
                {"phase": "candidate", "attempt": 1},
            )
        return "Ротируй на десять секунд раньше и удерживай сильную позицию."


class FakeProfiles:
    def get(self, chat_id: int):
        return {
            "game": "Warzone",
            "platform": "Xbox",
            "input": "Controller",
            "difficulty": "Pro",
            "voice": "TEAMMATE",
            "role": "Entry",
        }


class FakeStore:
    def __init__(self):
        self.history: list[dict] = []

    def add(self, chat_id: int, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def get(self, chat_id: int):
        return list(self.history)


def test_free_form_ai_uses_ephemeral_drafts_and_one_persistent_final_message():
    tg = FakeTelegram()
    brain = FakeBrain()
    store = FakeStore()
    router = Router(
        tg=tg,
        brain=brain,
        profiles=FakeProfiles(),
        store=store,
        settings=SimpleNamespace(telegram_live_drafts_enabled=True),
    )

    asyncio.run(router._chat_to_brain(8275036156, "Почему я поздно ротирую?"))

    assert brain.calls
    assert brain.calls[0]["profile"]["platform"] == "Xbox"
    assert tg.actions == [(8275036156, "typing")]
    assert tg.drafts
    assert any("LIVE INTELLIGENCE" in text for _, _, text in tg.drafts)
    assert len(tg.messages) == 1
    assert "Ротируй на десять секунд раньше" in tg.messages[0][1]
    assert store.history[0] == {"role": "user", "content": "Почему я поздно ротирую?"}
    assert store.history[-1]["role"] == "assistant"


def test_live_drafts_can_be_disabled_without_disabling_ai():
    tg = FakeTelegram()
    router = Router(
        tg=tg,
        brain=FakeBrain(),
        profiles=FakeProfiles(),
        store=FakeStore(),
        settings=SimpleNamespace(telegram_live_drafts_enabled=False),
    )

    asyncio.run(router._chat_to_brain(123, "Разбери позицию"))

    assert tg.drafts == []
    assert len(tg.messages) == 1
    assert "удерживай сильную позицию" in tg.messages[0][1]
