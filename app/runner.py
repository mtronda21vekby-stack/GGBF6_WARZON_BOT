# -*- coding: utf-8 -*-
import os
import time
import inspect

from app.log import log
from app.config import (
    TELEGRAM_BOT_TOKEN,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    HTTP_TIMEOUT,
    USER_AGENT,
    STATE_PATH,
)

from app.state import load_state, save_state
from app.telegram_api import TelegramAPI
from app.ai import AIEngine
from app.handlers import BotHandlers
from app.polling import poll_forever


def _build_handlers_kwargs(handlers_cls, *, api, ai_engine, log, state_path):
    """
    Передаём в BotHandlers ТОЛЬКО те параметры, которые он реально принимает.
    Это убирает краши "unexpected keyword argument".
    """
    sig = inspect.signature(handlers_cls.__init__)
    allowed = set(sig.parameters.keys()) - {"self"}

    candidates = {
        "api": api,
        "ai_engine": ai_engine,
        "log": log,
        "state_path": state_path,
        "state_file": state_path,   # на случай если у тебя так названо
        "data_dir": os.path.dirname(state_path),
    }
    return {k: v for k, v in candidates.items() if k in allowed}


def main():
    # 1) State
    try:
        load_state(STATE_PATH, log)
    except Exception as e:
        log.warning("State load failed: %r", e)

    # 2) Telegram API
    api = TelegramAPI(
        token=TELEGRAM_BOT_TOKEN,
        http_timeout=HTTP_TIMEOUT,
        user_agent=USER_AGENT,
        log=log,
    )

    # 3) AI engine
    ai_engine = AIEngine(
        openai_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
        log=log,
    )

    # 4) Handlers (без падений по kwargs)
    kwargs = _build_handlers_kwargs(
        BotHandlers,
        api=api,
        ai_engine=ai_engine,
        log=log,
        state_path=STATE_PATH,
    )
    handlers = BotHandlers(**kwargs)

    # 5) Polling (без webhook-конфликтов)
    poll_forever(api, handlers, log)

    # (на всякий случай — если poll_forever когда-то вернётся)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()