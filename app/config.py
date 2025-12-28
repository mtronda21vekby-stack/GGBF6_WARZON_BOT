# app/config.py
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Telegram ---
    bot_token: str = ""
    webhook_secret: str = ""  # X-Telegram-Bot-Api-Secret-Token (optional)

    # --- Logging ---
    log_level: str = "INFO"

    # --- Memory ---
    memory_max_turns: int = 20

    # --- AI (OpenAI) ---
    openai_api_key: str = ""         # put in Render ENV: OPENAI_API_KEY
    openai_model: str = "gpt-4.1-mini"  # быстрый/дешёвый. Потом можно поднять на сильнее.
    ai_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
