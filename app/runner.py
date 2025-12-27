# -*- coding: utf-8 -*-
import os
import time
import threading

from app.handlers import BotHandlers
from app.state import load_state, save_state, autosave_loop
from app.telegram_api import TelegramAPI
from app.brain.engine import AIEngine
from app.config import Config
from app.log import log


def main() -> None:
    cfg = Config.from_env()

    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    state_path = os.path.join(cfg.DATA_DIR, "state.json")

    load_state(state_path, log)

    api = TelegramAPI(
        token=cfg.TELEGRAM_BOT_TOKEN,
        http_timeout=cfg.HTTP_TIMEOUT,
        user_agent="render-fps-coach-bot/premium-v3",
        log=log
    )

    ai = AIEngine(
        openai_key=cfg.OPENAI_API_KEY,
        base_url=cfg.OPENAI_BASE_URL,
        model=cfg.OPENAI_MODEL,
        log=log
    )

    handlers = BotHandlers(api=api, ai_engine=ai, config=cfg, log=log)

    stop = threading.Event()
    t = threading.Thread(target=autosave_loop, args=(stop, state_path, log, cfg.AUTOSAVE_INTERVAL_S), daemon=True)
    t.start()

    api.delete_webhook_on_start()
    api.get_me_forever()

    offset = None
    log.info("BOT STARTED (premium reply keyboard, no inline). polling...")

    try:
        while True:
            data = api.request("getUpdates", params={"timeout": 30, "offset": offset})
            for upd in (data.get("result") or []):
                offset = (upd.get("update_id") or 0) + 1
                try:
                    handlers.handle_update(upd)
                except Exception as e:
                    log.exception("handle_update failed: %r", e)
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        save_state(state_path, log)
        log.info("BOT STOPPED")