# -*- coding: utf-8 -*-
import os
import threading
import time

from app.log import log
import app.config as config
from app.state import load_state, save_state
from app.telegram_api import TelegramAPI
from app.ai import AIEngine
from app.handlers import BotHandlers
from app.polling import poll_forever
from app.health import start_health_server


def main():
    # state
    try:
        load_state(config.STATE_PATH, log)
    except Exception as e:
        log.warning("State load failed: %r", e)

    # telegram
    api = TelegramAPI(
        token=config.TELEGRAM_BOT_TOKEN,
        http_timeout=config.HTTP_TIMEOUT,
        user_agent=config.USER_AGENT,
        log=log,
    )

    # ai
    ai_engine = AIEngine(
        openai_key=getattr(config, "OPENAI_API_KEY", ""),
        base_url=getattr(config, "OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=getattr(config, "OPENAI_MODEL", "gpt-4o-mini"),
        log=log,
    )

    # handlers (ВАЖНО: передаём config)
    handlers = BotHandlers(api=api, ai_engine=ai_engine, config=config, log=log)

    # Render Web Service требует PORT => поднимаем health сервер
    port = int(os.environ.get("PORT", "10000"))
    start_health_server(port=port, log=log)

    # polling
    poll_forever(api, handlers, log)

    # safety
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
