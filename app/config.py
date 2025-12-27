# -*- coding: utf-8 -*-
import os

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    # OpenAI (optional)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    # App
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip()
    TZ = os.getenv("TZ", "UTC").strip()

    MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "10"))
    DATA_DIR = os.getenv("DATA_DIR", "/tmp/ggbf6_bot").strip()
    STATE_PATH = os.path.join(DATA_DIR, "state.json")

    # Admin
    ADMIN_IDS = os.getenv("ADMIN_IDS", "").strip()  # "123,456"
    def admin_id_set(self):
        out = set()
        for x in self.ADMIN_IDS.split(","):
            x = x.strip()
            if x.isdigit():
                out.add(int(x))
        return out