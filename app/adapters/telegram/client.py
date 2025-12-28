from __future__ import annotations
import httpx


class TelegramClient:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base = f"https://api.telegram.org/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=25)

    async def close(self):
        await self._client.aclose()

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        r = await self._client.post(f"{self.base}/sendMessage", json=payload)
        r.raise_for_status()
        return r.json()

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None):
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        r = await self._client.post(f"{self.base}/answerCallbackQuery", json=payload)
        r.raise_for_status()
        return r.json()
