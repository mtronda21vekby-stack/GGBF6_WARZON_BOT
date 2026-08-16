# app/config.py
from __future__ import annotations

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except Exception:
    from pydantic import BaseSettings  # type: ignore


class Settings(BaseSettings):
    # Telegram
    bot_token: str = os.getenv("BOT_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Memory / persistence
    memory_max_turns: int = int(os.getenv("MEMORY_MAX_TURNS", "20"))
    storage_backend: str = os.getenv("STORAGE_BACKEND", "auto")
    storage_timeout_s: float = float(os.getenv("STORAGE_TIMEOUT_S", "8"))
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_schema: str = os.getenv("SUPABASE_SCHEMA", "public")

    # AI
    ai_enabled: bool = os.getenv("AI_ENABLED", "1") not in ("0", "false", "False", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    class Config:
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
