# -*- coding: utf-8 -*-
import random
import time
from typing import Any, Dict, Optional

import requests

from app.config import (
    TELEGRAM_BOT_TOKEN, HTTP_TIMEOUT, TG_LONGPOLL_TIMEOUT, TG_RETRIES,
    CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX, OFFSET_PATH, MAX_TEXT_LEN
)
from app.log import log
from app.handlers import handle_message, handle_callback

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/modular-v2"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=40))


def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.3)

def tg_request(method: str, *, params=None, payload=None, is_post: bool = False, retries: int = TG_RETRIES) -> Dict[str, Any]:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing ENV: TELEGRAM_BOT_TOKEN")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last: Optional[Exception] = None

    for i in range(max(1, retries)):
        try:
            if is_post:
                r = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT)
            else:
                r = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)

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

        _sleep_backoff(i)

    raise last or RuntimeError("Telegram request failed")

def send_message(chat_id: int, text: str, reply_markup=None) -> Optional[int]:
    text = text or ""
    chunks = [text[i:i + MAX_TEXT_LEN] for i in range(0, len(text), MAX_TEXT_LEN)] or [""]
    last_msg_id = None
    for ch in chunks:
        payload = {"chat_id": chat_id, "text": ch}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        res = tg_request("sendMessage", payload=payload, is_post=True)
        last_msg_id = res.get("result", {}).get("message_id")
    return last_msg_id

def edit_message(chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    tg_request("editMessageText", payload=payload, is_post=True)

def answer_callback(callback_id: str) -> None:
    try:
        tg_request("answerCallbackQuery", payload={"callback_query_id": callback_id}, is_post=True, retries=2)
    except Exception:
        pass


def delete_webhook_on_start() -> None:
    try:
        tg_request("deleteWebhook", payload={"drop_pending_updates": True}, is_post=True, retries=3)
        log.info("Webhook deleted (drop_pending_updates=true)")
    except Exception as e:
        log.warning("Could not delete webhook: %r", e)

def tg_getme_check_forever():
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing.")
        return
    while True:
        try:
            data = tg_request("getMe", retries=3)
            me = data.get("result") or {}
            log.info("Telegram getMe OK: @%s (id=%s)", me.get("username"), me.get("id"))
            return
        except Exception as e:
            log.error("Telegram getMe failed (will retry): %r", e)
            time.sleep(5)

def load_offset() -> int:
    try:
        import os
        if os.path.exists(OFFSET_PATH):
            with open(OFFSET_PATH, "r", encoding="utf-8") as f:
                return int((f.read() or "0").strip())
    except Exception:
        pass
    return 0

def save_offset(offset: int) -> None:
    try:
        tmp = OFFSET_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(int(offset)))
        import os
        os.replace(tmp, OFFSET_PATH)
    except Exception:
        pass

def run_telegram_bot_once() -> None:
    tg_getme_check_forever()
    if not TELEGRAM_BOT_TOKEN:
        return

    delete_webhook_on_start()
    log.info("Telegram bot started (long polling)")

    offset = load_offset()
    last_offset_save = time.time()

    while True:
        try:
            data = tg_request(
                "getUpdates",
                params={"offset": offset, "timeout": TG_LONGPOLL_TIMEOUT},
                is_post=False,
                retries=TG_RETRIES,
            )

            for upd in data.get("result", []):
                upd_id = upd.get("update_id")
                if isinstance(upd_id, int):
                    offset = max(offset, upd_id + 1)

                if "callback_query" in upd:
                    try:
                        handle_callback(upd["callback_query"])
                    except Exception:
                        log.exception("Callback handling error")
                    continue

                msg = upd.get("message") or upd.get("edited_message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue

                try:
                    handle_message(chat_id, text)
                except Exception:
                    log.exception("Message handling error")
                    try:
                        send_message(chat_id, "Ошибка 😅 Напиши ещё раз коротко.")
                    except Exception:
                        pass

            if time.time() - last_offset_save >= 5:
                save_offset(offset)
                last_offset_save = time.time()

        except RuntimeError as e:
            s = str(e)
            if "Conflict" in s and ("getUpdates" in s or "terminated by other getUpdates" in s):
                sleep_s = random.randint(CONFLICT_BACKOFF_MIN, CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict 409. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)
        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)

def run_telegram_bot_forever() -> None:
    while True:
        try:
            run_telegram_bot_once()
            if not TELEGRAM_BOT_TOKEN:
                time.sleep(30)
        except Exception:
            log.exception("Polling crashed — restarting in 3 seconds")
            time.sleep(3)
