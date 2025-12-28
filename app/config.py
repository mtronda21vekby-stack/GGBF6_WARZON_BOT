from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBHOOK_SECRET: str | None = None

    # Brain/memory
    memory_max_turns: int = 20

    # Logs
    log_level: str = "INFO"

    # AI
    AI_ENABLED: bool = True
    AI_API_KEY: str | None = None
    AI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL: str = "gpt-4o-mini"
    AI_TIMEOUT_SEC: int = 25

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
