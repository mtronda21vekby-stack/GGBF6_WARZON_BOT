# -*- coding: utf-8 -*-
from __future__ import annotations
import httpx
from typing import Any, Dict, Optional

class TelegramClient:
    def __init__(self, token: str):
        self._base = f"https://api.telegram.org/bot{token}"
        self._http = httpx.AsyncClient(timeout=30)

    async def close(self) -> None:
        await self._http.aclose()

    async def request(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base}/{method}"
        r = await self._http.post(url, json=payload)
        r.raise_for_status()
        return r.json()

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self.request("sendMessage", payload)

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = False
        return await self.request("answerCallbackQuery", payload)
