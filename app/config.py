# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass

@dataclass
class Config:
    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str
    OPENAI_MODEL: str
    DATA_DIR: str
    HTTP_TIMEOUT: float
    AUTOSAVE_INTERVAL_S: int
    MEMORY_MAX_TURNS: int

    @staticmethod
    def from_env() -> "Config":
        return Config(
            TELEGRAM_BOT_TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", "").strip(),
            OPENAI_BASE_URL=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            OPENAI_MODEL=os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip(),
            DATA_DIR=os.environ.get("DATA_DIR", "/tmp").strip(),
            HTTP_TIMEOUT=float(os.environ.get("HTTP_TIMEOUT", "30")),
            AUTOSAVE_INTERVAL_S=int(os.environ.get("AUTOSAVE_INTERVAL_S", "60")),
            MEMORY_MAX_TURNS=int(os.environ.get("MEMORY_MAX_TURNS", "10")),
        )