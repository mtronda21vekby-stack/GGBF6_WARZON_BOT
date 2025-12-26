import os
import sys
import threading
import time

from app.config import load_settings
from app.log import setup_logger
from app.state import load_state, autosave_loop, save_state
from app.telegram_api import TelegramAPI
from app.ai import AIEngine
from app.handlers import BotHandlers
from app.polling import run_telegram_bot_forever
from app.health import run_http_server

def startup_diagnostics(log, settings, ai_engine):
    try:
        log.info("=== STARTUP DIAGNOSTICS ===")
        log.info("python: %s", sys.version.replace("\n", " "))
        log.info("cwd: %s", os.getcwd())
        log.info("DATA_DIR=%s", settings.DATA_DIR)
        log.info("STATE_PATH=%s", settings.STATE_PATH)
        log.info("OFFSET_PATH=%s", settings.OFFSET_PATH)
        log.info("OPENAI_BASE_URL=%s", settings.OPENAI_BASE_URL)
        log.info("OPENAI_MODEL=%s", settings.OPENAI_MODEL)
        log.info("TELEGRAM_BOT_TOKEN present: %s", True)
        log.info("OPENAI_API_KEY present: %s", bool(settings.OPENAI_API_KEY))
        log.info("openai enabled: %s", ai_engine.enabled)
        log.info("===========================")
    except Exception:
        pass

def main():
    log = setup_logger()
    try:
        settings = load_settings()
        os.makedirs(settings.DATA_DIR, exist_ok=True)

        ai_engine = AIEngine(
            openai_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            log=log,
        )
        startup_diagnostics(log, settings, ai_engine)

        load_state(settings.STATE_PATH, log)

        api = TelegramAPI(
            token=settings.TELEGRAM_BOT_TOKEN,
            http_timeout=settings.HTTP_TIMEOUT,
            user_agent="render-fps-coach-bot/clean-smart-v2-split",
            log=log,
        )

        handlers = BotHandlers(api=api, ai_engine=ai_engine, settings=settings, log=log)

        stop_autosave = threading.Event()
        threading.Thread(target=autosave_loop, args=(stop_autosave, settings.STATE_PATH, log, 60), daemon=True).start()

        threading.Thread(target=run_telegram_bot_forever, args=(api, handlers, settings, log), daemon=True).start()

        run_http_server(log)

    except Exception:
        log.exception("FATAL STARTUP ERROR")
        while True:
            time.sleep(60)
