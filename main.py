# main.py
# -*- coding: utf-8 -*-

import threading
import time
import traceback

from app.log import log
from app.config import startup_diagnostics
from app.state import load_state, autosave_loop
from app.tg import run_telegram_bot_forever
from app.health import run_http_server


if __name__ == "__main__":
    try:
        startup_diagnostics()
        load_state()

        stop_autosave = threading.Event()
        threading.Thread(
            target=autosave_loop,
            args=(stop_autosave, 60),
            daemon=True
        ).start()

        threading.Thread(
            target=run_telegram_bot_forever,
            daemon=True
        ).start()

        run_http_server()

    except Exception:
        log.error("FATAL STARTUP ERROR:\n%s", traceback.format_exc())
        while True:
            time.sleep(60)
