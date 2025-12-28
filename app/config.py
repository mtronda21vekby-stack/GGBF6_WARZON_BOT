# app/config.py
from __future__ import annotations

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except Exception:
    # fallback если вдруг старая сборка — но лучше поставить pydantic-settings в requirements
    from pydantic import BaseSettings  # type: ignore


class Settings(BaseSettings):
    # Telegram
    bot_token: str = os.getenv("BOT_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Memory
    memory_max_turns: int = int(os.getenv("MEMORY_MAX_TURNS", "20"))

    # AI
    ai_enabled: bool = os.getenv("AI_ENABLED", "1") not in ("0", "false", "False", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    class Config:
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    return s
