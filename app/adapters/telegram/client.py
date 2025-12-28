# app/adapters/telegram/client.py
from __future__ import annotations

import os
import httpx


class TelegramClient:
    def __init__(self, bot_token: str):
        self._token = bot_token
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=60)

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

    async def send_animation_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        """
        Отправляет mp4/gif как animation (то, что выглядит как “баннер/анимация”).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Animation file not found: {file_path}")

        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if reply_markup is not None:
            # Telegram Bot API ждёт JSON-строку
            import json
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

        with open(file_path, "rb") as f:
            files = {"animation": (os.path.basename(file_path), f, "video/mp4")}
            r = await self._client.post(f"{self._base}/sendAnimation", data=data, files=files)
            r.raise_for_status()

    async def send_video_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        """
        Если animation вдруг не понравится — можно слать как video.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if reply_markup is not None:
            import json
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

        with open(file_path, "rb") as f:
            files = {"video": (os.path.basename(file_path), f, "video/mp4")}
            r = await self._client.post(f"{self._base}/sendVideo", data=data, files=files)
            r.raise_for_status()
