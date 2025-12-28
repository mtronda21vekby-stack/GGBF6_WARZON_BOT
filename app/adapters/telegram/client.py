# app/adapters/telegram/client.py
from __future__ import annotations

import httpx


class TelegramClient:
    def __init__(self, bot_token: str):
        self._token = bot_token
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=20)

    async def close(self) -> None:
        await self._client.aclose()

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        r = await self._client.post(f"{self._base}/sendMessage", json=payload)
        r.raise_for_status()
