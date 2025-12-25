# app/log.py
# -*- coding: utf-8 -*-

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("fps_coach_modular_v2")


def startup_diagnostics():
    """
    Диагностика запуска.
    ВАЖНО: импорт config делаем внутри функции, чтобы не ловить циклические импорты.
    """
    try:
        from app import config  # <-- только здесь

        log.info("=== STARTUP DIAGNOSTICS ===")
        log.info("python: %s", sys.version.replace("\n", " "))
        log.info("cwd: %s", os.getcwd())
        log.info("DATA_DIR=%s", getattr(config, "DATA_DIR", None))
        log.info("STATE_PATH=%s", getattr(config, "STATE_PATH", None))
        log.info("OFFSET_PATH=%s", getattr(config, "OFFSET_PATH", None))
        log.info("OPENAI_BASE_URL=%s", getattr(config, "OPENAI_BASE_URL", None))
        log.info("OPENAI_MODEL=%s", getattr(config, "OPENAI_MODEL", None))
        log.info("TELEGRAM_BOT_TOKEN present: %s", bool(getattr(config, "TELEGRAM_BOT_TOKEN", "")))
        log.info("OPENAI_API_KEY present: %s", bool(getattr(config, "OPENAI_API_KEY", "")))
        log.info("===========================")
    except Exception:
        # не валим запуск из-за диагностики
        pass
