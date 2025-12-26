# -*- coding: utf-8 -*-
"""
Главный runner бота.
Без веб-сервера Telegram, только polling + health-check для Render.
Максимально совместим со старым кодом.
"""

import os
import time
import traceback

from app.log import log
from app.health import start_health_server
from app.telegram_api import TelegramAPI
from app.ai import AIEngine

# handlers может иметь разную сигнатуру — учитываем это
from app.handlers import BotHandlers


def main():
    log.info("=" * 50)
    log.info("STARTING BOT RUNNER")

    # ----------------------------
    # ENV
    # ----------------------------
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30"))

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    # ----------------------------
    # HEALTH SERVER (Render fix)
    # ----------------------------
    start_health_server(log)

    # ----------------------------
    # Telegram API
    # ----------------------------
    api = TelegramAPI(
        token=TELEGRAM_BOT_TOKEN,
        http_timeout=HTTP_TIMEOUT,
        user_agent="ggbf6-warzone-bot",
        log=log,
    )

    api.delete_webhook_on_start()
    api.get_me_forever()

    # ----------------------------
    # AI ENGINE
    # ----------------------------
    ai_engine = AIEngine(
        openai_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
        log=log,
    )

    log.info("openai enabled: %s", ai_engine.enabled)

    # ----------------------------
    # HANDLERS (SAFE INIT)
    # ----------------------------
    try:
        handlers = BotHandlers(api=api, ai_engine=ai_engine)
    except TypeError:
        # fallback для старых версий handlers.py
        try:
            handlers = BotHandlers(api, ai_engine)
        except Exception:
            handlers = BotHandlers(api)

    # ----------------------------
    # POLLING LOOP
    # ----------------------------
    offset = 0
    log.info("Polling started")

    while True:
        try:
            updates = api.request(
                "getUpdates",
                params={
                    "timeout": 30,
                    "offset": offset,
                    "allowed_updates": ["message", "callback_query"],
                },
            )

            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1

                # callback кнопки
                if "callback_query" in upd:
                    handlers.on_callback(upd["callback_query"])
                    continue

                # обычные сообщения
                if "message" in upd:
                    handlers.on_message(upd["message"])

        except KeyboardInterrupt:
            log.warning("Bot stopped by keyboard")
            break

        except Exception as e:
            log.error("Polling error: %r", e)
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    main()
