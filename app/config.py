# app/config.py
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Telegram
    bot_token: str
    webhook_secret: str | None

    # Brain / memory
    memory_max_turns: int

    # Logging
    log_level: str

    # AI (на будущее, ключ держи ТОЛЬКО в переменных окружения)
    openai_api_key: str | None


_cached: Settings | None = None


def get_settings() -> Settings:
    global _cached
    if _cached is not None:
        return _cached

    bot_token = _env("BOT_TOKEN") or _env("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        # не падаем “непонятно где”, а даём явный текст
        raise RuntimeError("ENV BOT_TOKEN is required (Telegram bot token).")

    _cached = Settings(
        bot_token=bot_token,
        webhook_secret=_env("WEBHOOK_SECRET"),
        memory_max_turns=_env_int("MEMORY_MAX_TURNS", 20),
        log_level=_env("LOG_LEVEL", "INFO") or "INFO",
        openai_api_key=_env("OPENAI_API_KEY"),
    )
    return _cached
