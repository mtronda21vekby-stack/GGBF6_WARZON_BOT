# -*- coding: utf-8 -*-
import os
import sys
import logging

# ===== Logging =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("fps_coach")

# ===== ENV =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DATA_DIR = os.getenv("DATA_DIR", "/tmp").strip()
STATE_PATH = os.path.join(DATA_DIR, "fps_coach_state.json")
OFFSET_PATH = os.path.join(DATA_DIR, "tg_offset.txt")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
TG_LONGPOLL_TIMEOUT = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
TG_RETRIES = int(os.getenv("TG_RETRIES", "6"))

CONFLICT_BACKOFF_MIN = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
CONFLICT_BACKOFF_MAX = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

MIN_SECONDS_BETWEEN_MSG = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.25"))
MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))

MAX_TEXT_LEN = 3900

def startup_diagnostics():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        log.info("=== STARTUP DIAGNOSTICS ===")
        log.info("python: %s", sys.version.replace("\n", " "))
        log.info("cwd: %s", os.getcwd())
        log.info("DATA_DIR=%s", DATA_DIR)
        log.info("STATE_PATH=%s", STATE_PATH)
        log.info("OFFSET_PATH=%s", OFFSET_PATH)
        log.info("OPENAI_BASE_URL=%s", OPENAI_BASE_URL)
        log.info("OPENAI_MODEL=%s", OPENAI_MODEL)
        log.info("TELEGRAM_BOT_TOKEN present: %s", bool(TELEGRAM_BOT_TOKEN))
        log.info("OPENAI_API_KEY present: %s", bool(OPENAI_API_KEY))
        log.info("===========================")
    except Exception:
        pass
