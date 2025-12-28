from __future__ import annotations

import httpx


class TelegramClient:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=20.0)

    async def close(self):
        await self._client.aclose()

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup  # dict для ReplyKeyboardMarkup
        r = await self._client.post(f"{self.base}/sendMessage", json=payload)
        r.raise_for_status()
        return r.json()
