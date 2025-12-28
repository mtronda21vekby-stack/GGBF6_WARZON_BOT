from __future__ import annotations

import os
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 🔐 Telegram
    BOT_TOKEN: str
    WEBHOOK_SECRET: str = "secret"
    PUBLIC_URL: str | None = None

    # 🧠 AI
    AI_ENABLED: bool = True
    AI_MODEL: str = "gpt-4.1-mini"

    # ⚙️ App
    APP_NAME: str = "GGBF6 WARZONE BOT"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
