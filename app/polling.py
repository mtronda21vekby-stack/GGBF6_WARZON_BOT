# -*- coding: utf-8 -*-
import time
from typing import Any, Dict, Optional


def _is_conflict(err: str) -> bool:
    # Telegram 409: "Conflict: terminated by other getUpdates request"
    return "Conflict" in err and "getUpdates" in err


def poll_forever(api, handlers, log, *, timeout: int = 50) -> None:
    """
    Надёжный long-polling для Telegram.
    - Убирает webhook
    - Держит offset
    - Логирует реальную причину ошибок
    """
    # 1) гарантируем polling-режим
    api.delete_webhook_on_start()
    api.get_me_forever()

    offset: Optional[int] = None
    log.info("BOT STARTED (polling)")

    while True:
        try:
            params: Dict[str, Any] = {
                "timeout": timeout,
                "allowed_updates": ["message", "edited_message", "callback_query"],
            }
            if offset is not None:
                params["offset"] = offset

            data = api.request("getUpdates", params=params, is_post=False, retries=3)
            updates = data.get("result") or []

            for upd in updates:
                try:
                    upd_id = upd.get("update_id")
                    if isinstance(upd_id, int):
                        offset = upd_id + 1
                    handlers.handle_update(upd)
                except Exception as e:
                    log.exception("update handling error: %r", e)

        except Exception as e:
            # ✅ ВАЖНО: показываем реальную причину
            msg = repr(e)
            log.error("poll loop error: %s", msg)

            # 409 — почти всегда две копии polling одновременно
            if _is_conflict(msg):
                log.error("Telegram 409 Conflict: похоже запущены 2 копии бота. Проверь Render concurrency/второй деплой.")
                time.sleep(5)
                continue

            time.sleep(2)