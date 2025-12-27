# -*- coding: utf-8 -*-
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

DATA_DIR = os.getenv("DATA_DIR", "/tmp/data").strip()
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))
USER_AGENT = os.getenv("USER_AGENT", "render-fps-coach-bot/premium-v3").strip()

POLL_LIMIT = int(os.getenv("POLL_LIMIT", "50"))
POLL_TIMEOUT = int(os.getenv("POLL_TIMEOUT", "45"))
