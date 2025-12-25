# main.py
# -*- coding: utf-8 -*-

import threading
import time
import traceback


# ===== config import (SAFE) =====
# Если app/config.py не импортится (Render/пути/файл/регистр) — бот НЕ падает,
# а запускается с запасным логгером и диагностикой.
try:
    from app.config import log, startup_diagnostics
except Exception:
    import os
    import sys
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    log = logging.getLogger("fps_coach_fallback")

    def startup_diagnostics():
        try:
            log.info("=== STARTUP DIAGNOSTICS (FALLBACK) ===")
            log.info("python: %s", sys.version.replace("\n", " "))
            log.info("cwd: %s", os.getcwd())
            log.info("=======================================")
        except Exception:
            pass
# ===============================


from app.state import load_state, autosave_loop
from app.telegram_polling import run_telegram_bot_forever
from app.http_server import run_http_server


if __name__ == "__main__":
    try:
        startup_diagnostics()
        load_state()

        stop_autosave = threading.Event()
        threading.Thread(target=autosave_loop, args=(stop_autosave, 60), daemon=True).start()

        threading.Thread(target=run_telegram_bot_forever, daemon=True).start()
        run_http_server()

    except Exception:
        log.error("FATAL STARTUP ERROR:\n%s", traceback.format_exc())
        while True:
            time.sleep(60)
