# app/config.py  (ЕСЛИ У ТЕБЯ НЕТ — СОЗДАЙ И ВСТАВЬ)
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    bot_token: str
    webhook_secret: str | None = None


def get_settings() -> Settings:
    return Settings(
        bot_token=os.environ.get("BOT_TOKEN", "").strip(),
        webhook_secret=os.environ.get("WEBHOOK_SECRET", "").strip() or None,
    )
