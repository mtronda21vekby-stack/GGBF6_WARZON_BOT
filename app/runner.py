# -*- coding: utf-8 -*-
import time

from app.config import Config
from app.log import log
from app.state import load_state, save_state
from app.health import start_health_server
from app.telegram_api import TelegramAPI
from app.ai import AIEngine
from app.brain_v3 import BrainV3
from app.handlers import BotHandlers
from app.polling import PollingLoop

def main():
    cfg = Config()

    if not cfg.TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing. Set it in Render env vars.")
        raise SystemExit(1)

    # 1) health server for Render web service
    start_health_server(log)

    # 2) state
    load_state(cfg.STATE_PATH, log)

    # 3) telegram
    api = TelegramAPI(cfg.TELEGRAM_BOT_TOKEN, log=log)
    try:
        api.delete_webhook(drop_pending_updates=True)
        me = api.get_me()
        log.info("telegram: getMe ok=%s username=%s", me.get("ok"), (me.get("result") or {}).get("username"))
    except Exception as e:
        log.warning("telegram init failed: %r", e)

    # 4) ai + brain
    ai = AIEngine(api_key=cfg.OPENAI_API_KEY, model=cfg.OPENAI_MODEL, log=log)
    brain = BrainV3(ai_engine=ai, log=log, cfg=cfg)

    # 5) handlers + polling
    handlers = BotHandlers(api=api, brain=brain, config=cfg, log=log)
    loop = PollingLoop(api=api, handlers=handlers, log=log)

    # периодически сохраняем state
    last_save = time.time()

    while True:
        try:
            loop.run_forever()
        finally:
            # на всякий случай
            now = time.time()
            if now - last_save > 10:
                save_state(cfg.STATE_PATH, log)
                last_save = now
