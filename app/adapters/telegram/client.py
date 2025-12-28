# app/adapters/telegram/client.py  (ЗАМЕНИ ЦЕЛИКОМ)
from __future__ import annotations

import requests


class TelegramClient:
    def __init__(self, token: str):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup  # dict (ReplyKeyboardMarkup)
        r = requests.post(f"{self.base}/sendMessage", json=payload, timeout=20)
        r.raise_for_status()
