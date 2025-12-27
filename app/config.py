# -*- coding: utf-8 -*-
import os
import logging
from dataclasses import dataclass


def _log():
    log = logging.getLogger("bot")
    if not log.handlers:
        logging.basicConfig(level=logging.INFO)
    return log


@dataclass
class Config:
    TELEGRAM_BOT_TOKEN: str
    WEBHOOK_SECRET: str

    # OpenAI (опционально)
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str
    OPENAI_MODEL: str

    # прочее
    HTTP_TIMEOUT: float = 30.0
    USER_AGENT: str = "GGBF6_WARZON_BOT/BrainV3"
    DATA_DIR: str = "data"
    MEMORY_MAX_TURNS: int = 10

    log = _log()

    @staticmethod
    def from_env() -> "Config":
        return Config(
            TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET", "").strip(),

            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", "").strip(),
            OPENAI_BASE_URL=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            OPENAI_MODEL=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),

            HTTP_TIMEOUT=float(os.getenv("HTTP_TIMEOUT", "30")),
            USER_AGENT=os.getenv("USER_AGENT", "GGBF6_WARZON_BOT/BrainV3").strip(),
            DATA_DIR=os.getenv("DATA_DIR", "data").strip(),
            MEMORY_MAX_TURNS=int(os.getenv("MEMORY_MAX_TURNS", "10")),
        )
