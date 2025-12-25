# app/tg.py
# -*- coding: utf-8 -*-

import random
import time
from typing import Any, Dict, Optional

import requests

from app import config
from app.log import log
from app.handlers import handle_message, handle_callback

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "render-fps-coach-bot/modular-v2"})
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=40))


def _sleep_backoff(i: int) -> None:
    time.sleep((0.6 * (i + 1)) + random.random() * 0.3)


def tg_request(method: str, *, params=None, payload=None, is_post: bool = False, retries: int = None) -> Dict[str, Any]:
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing ENV: TELEGRAM_BOT_TOKEN")

    if retries is None:
        retries = config.TG_RETRIES

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"
    last: Optional[Exception] = None

    for i in range(max(1, retries)):
        try:
            if is_post:
                r = SESSION.post(url, json=payload, timeout=config.HTTP_TIMEOUT)
            else:
                r = SESSION.get(url, params=params, timeout=config.HTTP_TIMEOUT)

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
    chunks = [text[i:i + config.MAX_TEXT_LEN] for i in range(0, len(text), config.MAX_TEXT_LEN)] or [""]

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


def load_offset() -> int:
    try:
        import os
        if os.path.exists(config.OFFSET_PATH):
            with open(config.OFFSET_PATH, "r", encoding="utf-8") as f:
                return int((f.read() or "0").strip())
    except Exception:
        pass
    return 0


def save_offset(offset: int) -> None:
    try:
        import os
        tmp = config.OFFSET_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(int(offset)))
        os.replace(tmp, config.OFFSET_PATH)
    except Exception:
        pass


def run_telegram_bot_forever() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing.")
        while True:
            time.sleep(30)

    delete_webhook_on_start()
    log.info("Telegram bot started (long polling)")

    offset = load_offset()

    while True:
        try:
            data = tg_request(
                "getUpdates",
                params={"offset": offset, "timeout": config.TG_LONGPOLL_TIMEOUT},
                is_post=False,
                retries=config.TG_RETRIES,
            )

            for upd in data.get("result", []):
                upd_id = upd.get("update_id")
                if isinstance(upd_id, int):
                    offset = max(offset, upd_id + 1)
                    # ✅ ВАЖНО: сохраняем offset СРАЗУ, чтобы не было дублей после рестарта
                    save_offset(offset)

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

        except RuntimeError as e:
            s = str(e)
            if "Conflict" in s and ("getUpdates" in s or "terminated by other getUpdates" in s):
                sleep_s = random.randint(config.CONFLICT_BACKOFF_MIN, config.CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict 409. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)
        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)
