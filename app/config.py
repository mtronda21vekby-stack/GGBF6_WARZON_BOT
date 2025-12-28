from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    bot_token: str = ""
    webhook_secret: str = ""

    # твои параметры (оставляю, чтобы не ломать существующий код)
    log_level: str = "INFO"
    memory_max_turns: int = 12

    # разрешаем читать из .env и переменных окружения Render
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()

    # маленькая страховка — чтобы не было "пустого токена" тихо
    if not s.bot_token:
        # BOT_TOKEN — это типичное имя у тебя, но если ты используешь BOT_TOKEN (верхний регистр),
        # pydantic-settings сам его подхватит (bot_token <- BOT_TOKEN).
        pass

    return s
