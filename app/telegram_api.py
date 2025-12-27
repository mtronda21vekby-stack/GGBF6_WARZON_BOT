# -*- coding: utf-8 -*-
import requests
from typing import Any, Dict, Optional

class TelegramAPI:
    def __init__(self, token: str, *, log, timeout: int = 60):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout
        self.log = log
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "ggbf6-bot/brainv3"})

    def _post(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/{method}"
        r = self.s.post(url, json=payload, timeout=self.timeout)
        return r.json()

    def _get(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base}/{method}"
        r = self.s.get(url, params=params or {}, timeout=self.timeout)
        return r.json()

    def get_me(self) -> Dict[str, Any]:
        return self._get("getMe")

    def delete_webhook(self, drop_pending_updates: bool = True) -> Dict[str, Any]:
        return self._post("deleteWebhook", {"drop_pending_updates": drop_pending_updates})

    def get_updates(self, offset: int, timeout: int = 50) -> Dict[str, Any]:
        return self._get("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": ["message","edited_message","callback_query"]})

    def send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._post("sendMessage", payload)

    def answer_callback(self, callback_query_id: str, text: str = "") -> Dict[str, Any]:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return self._post("answerCallbackQuery", payload)