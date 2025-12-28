# app/config.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    ВАЖНО:
    - Мы используем snake_case в коде: settings.bot_token
    - А в переменных окружения Render обычно UPPER_CASE: BOT_TOKEN
    """

    # Telegram
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    webhook_secret: str = Field(default="", alias="WEBHOOK_SECRET")

    # App
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    memory_max_turns: int = Field(default=12, alias="MEMORY_MAX_TURNS")

    # AI (на будущее, уже предусмотрено)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,  # чтобы работали alias'ы
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
