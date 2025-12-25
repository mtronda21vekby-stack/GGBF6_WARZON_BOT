# app/log.py
# -*- coding: utf-8 -*-

import logging
import os
import sys
from app import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("fps_coach_modular_v2")

def startup_diagnostics():
    try:
        log.info("=== STARTUP DIAGNOSTICS ===")
        log.info("python: %s", sys.version.replace("\n", " "))
        log.info("cwd: %s", os.getcwd())
        log.info("DATA_DIR=%s", config.DATA_DIR)
        log.info("STATE_PATH=%s", config.STATE_PATH)
        log.info("OFFSET_PATH=%s", config.OFFSET_PATH)
        log.info("OPENAI_BASE_URL=%s", config.OPENAI_BASE_URL)
        log.info("OPENAI_MODEL=%s", config.OPENAI_MODEL)
        log.info("TELEGRAM_BOT_TOKEN present: %s", bool(config.TELEGRAM_BOT_TOKEN))
        log.info("OPENAI_API_KEY present: %s", bool(config.OPENAI_API_KEY))
        log.info("===========================")
    except Exception:
        pass
