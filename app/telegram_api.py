import time
import random
from typing import Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter

class TelegramAPI:
    def __init__(self, token: str, http_timeout: float, user_agent: str, log):
        self.token = token
        self.http_timeout = http_timeout
        self.log = log

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.session.mount("https://", HTTPAdapter(pool_connections=40, pool_maxsize=40))

    def _sleep_backoff(self, i: int) -> None:
        time.sleep((0.6 * (i + 1)) + random.random() * 0.3)

    def request(self, method: str, *, params=None, payload=None, is_post: bool = False, retries: int = 6) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("Missing ENV: TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{self.token}/{method}"

        last: Optional[Exception] = None
        for i in range(max(1, retries)):
            try:
                if is_post:
                    r = self.session.post(url, json=payload, timeout=self.http_timeout)
                else:
                    r = self.session.get(url, params=params, timeout=self.http_timeout)

                data = r.json()
                if r.status_code == 200 and data.get("ok"):
                    return data

                desc = data.get("description", f"Telegram HTTP {r.status_code}")
                last = RuntimeError(desc)

                params_ = data.get("parameters") or {}
                retry_after = params_.get("retry_after")
                if isinstance(retry_after, int) and retry_after > 0:
                    time.sleep(min(30, retry_after))
                    continue

            except Exception as e:
                last = e

            self._sleep_backoff(i)

        raise last or RuntimeError("Telegram request failed")

    def get_me_forever(self) -> None:
        while True:
            try:
                data = self.request("getMe", retries=3)
                me = data.get("result") or {}
                self.log.info("Telegram getMe OK: @%s (id=%s)", me.get("username"), me.get("id"))
                return
            except Exception as e:
                self.log.error("Telegram getMe failed (will retry): %r", e)
                time.sleep(5)

    def delete_webhook_on_start(self) -> None:
        try:
            self.request("deleteWebhook", payload={"drop_pending_updates": True}, is_post=True, retries=3)
            self.log.info("Webhook deleted (drop_pending_updates=true)")
        except Exception as e:
            self.log.warning("Could not delete webhook: %r", e)

    def answer_callback(self, callback_id: str) -> None:
        try:
            self.request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True, retries=2)
        except Exception:
            pass

    def send_message(self, chat_id: int, text: str, reply_markup=None, max_text_len: int = 3900) -> Optional[int]:
        text = text or ""
        chunks = [text[i:i + max_text_len] for i in range(0, len(text), max_text_len)] or [""]
        last_msg_id = None
        for ch in chunks:
            payload = {"chat_id": chat_id, "text": ch}
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            res = self.request("sendMessage", payload=payload, is_post=True)
            last_msg_id = res.get("result", {}).get("message_id")
        return last_msg_id

    def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        self.request("editMessageText", payload=payload, is_post=True)
