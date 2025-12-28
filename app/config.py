# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBHOOK_SECRET: str | None = None

    # Brain / memory
    memory_max_turns: int = 20

    # Logs
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
