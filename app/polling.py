import os
import time
import random

def load_offset(offset_path: str) -> int:
    try:
        if os.path.exists(offset_path):
            with open(offset_path, "r", encoding="utf-8") as f:
                return int((f.read() or "0").strip())
    except Exception:
        pass
    return 0

def save_offset(offset_path: str, offset: int) -> None:
    try:
        tmp = offset_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(int(offset)))
        os.replace(tmp, offset_path)
    except Exception:
        pass

def run_telegram_bot_once(api, handlers, settings, log) -> None:
    api.get_me_forever()
    api.delete_webhook_on_start()

    log.info("Telegram bot started (long polling)")
    offset = load_offset(settings.OFFSET_PATH)
    last_offset_save = time.time()

    while True:
        try:
            data = api.request(
                "getUpdates",
                params={"offset": offset, "timeout": settings.TG_LONGPOLL_TIMEOUT},
                is_post=False,
                retries=settings.TG_RETRIES,
            )

            for upd in data.get("result", []):
                upd_id = upd.get("update_id")
                if isinstance(upd_id, int):
                    offset = max(offset, upd_id + 1)

                if "callback_query" in upd:
                    try:
                        handlers.handle_callback(upd["callback_query"])
                    except Exception:
                        log.exception("Callback handling error")
                    continue

                msg = upd.get("message") or upd.get("edited_message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue

                try:
                    handlers.handle_message(chat_id, text)
                except Exception:
                    log.exception("Message handling error")
                    try:
                        api.send_message(chat_id, "Ошибка 😅 Напиши ещё раз коротко.", reply_markup=None, max_text_len=settings.MAX_TEXT_LEN)
                    except Exception:
                        pass

            if time.time() - last_offset_save >= 5:
                save_offset(settings.OFFSET_PATH, offset)
                last_offset_save = time.time()

        except RuntimeError as e:
            s = str(e)
            if "Conflict" in s and ("getUpdates" in s or "terminated by other getUpdates" in s):
                sleep_s = random.randint(settings.CONFLICT_BACKOFF_MIN, settings.CONFLICT_BACKOFF_MAX)
                log.warning("Telegram conflict 409. Backoff %ss: %s", sleep_s, s)
                time.sleep(sleep_s)
                continue
            log.warning("Loop RuntimeError: %r", e)
            time.sleep(2)
        except Exception as e:
            log.warning("Loop error: %r", e)
            time.sleep(2)

def run_telegram_bot_forever(api, handlers, settings, log) -> None:
    while True:
        try:
            run_telegram_bot_once(api, handlers, settings, log)
            time.sleep(3)
        except Exception:
            log.exception("Polling crashed — restarting in 3 seconds")
            time.sleep(3)
