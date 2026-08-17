from __future__ import annotations

import asyncio
import json

import httpx

from app.adapters.telegram.client import TelegramClient
from app.services.telegram.live_response import TelegramLiveResponse


class FakeTelegram:
    def __init__(self, mode: str = "rich"):
        self.mode = mode
        self.drafts: list[tuple[int, int, str]] = []

    async def send_live_draft(self, chat_id: int, draft_id: int, text: str) -> str:
        self.drafts.append((chat_id, draft_id, text))
        return self.mode


def test_live_response_coalesces_updates_and_finishes_with_final_preview():
    async def scenario():
        tg = FakeTelegram()
        session = TelegramLiveResponse(tg=tg, chat_id=42, min_interval_s=0.01)
        await session.start()
        session.publish_from_thread("Первая часть", {"phase": "generating", "attempt": 1})
        session.publish_from_thread("Первая часть. Вторая часть", {"phase": "candidate", "attempt": 1})
        await asyncio.sleep(0.04)
        await session.finish("Финальный тактический ответ")
        return tg.drafts

    drafts = asyncio.run(scenario())
    assert drafts
    assert all(chat_id == 42 for chat_id, _, _ in drafts)
    assert any("LIVE INTELLIGENCE" in text for _, _, text in drafts)
    assert "Финальный тактический ответ" in drafts[-1][2]


def test_unsupported_drafts_disable_preview_without_raising():
    async def scenario():
        tg = FakeTelegram(mode="unsupported")
        session = TelegramLiveResponse(tg=tg, chat_id=7, min_interval_s=0.01)
        await session.start()
        await asyncio.sleep(0.03)
        session.publish_from_thread("ignored", {"phase": "generating"})
        await session.finish("final")
        return tg.drafts

    drafts = asyncio.run(scenario())
    assert len(drafts) >= 1


def test_telegram_client_prefers_rich_draft_and_falls_back_to_text():
    requests: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/sendRichMessageDraft"):
            return httpx.Response(404, json={"ok": False, "description": "method not found"})
        return httpx.Response(200, json={"ok": True, "result": True})

    async def scenario():
        client = TelegramClient("TEST")
        await client._client.aclose()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await client.send_live_draft(
                123,
                55,
                "◼ BLACK CROWN OPS // LIVE INTELLIGENCE\n──────────────\nАнализирую позицию",
            )
        finally:
            await client.close()

    mode = asyncio.run(scenario())
    assert mode == "plain"
    assert [path for path, _ in requests] == [
        "/botTEST/sendRichMessageDraft",
        "/botTEST/sendMessageDraft",
    ]
    assert requests[0][1]["draft_id"] == 55
    assert "rich_message" in requests[0][1]
    assert requests[1][1]["text"].startswith("◼ BLACK CROWN OPS")
