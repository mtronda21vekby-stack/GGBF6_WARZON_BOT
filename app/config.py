# app/config.py
from pydantic import BaseSettings


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBHOOK_SECRET: str | None = None

    # Memory / brain
    memory_max_turns: int = 20

    # Logs
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings