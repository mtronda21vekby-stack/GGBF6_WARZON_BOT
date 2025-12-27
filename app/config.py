# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    bot_token: str
    webhook_secret: str
    tz: str
    log_level: str
    openai_api_key: str | None
    openai_model: str
    memory_max_turns: int
    admin_ids: set[int]

def _parse_admin_ids(raw: str) -> set[int]:
    out: set[int] = set()
    raw = (raw or "").strip()
    if not raw:
        return out
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out

def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    return Settings(
        bot_token=bot_token,
        webhook_secret=os.getenv("WEBHOOK_SECRET", "change-me-secret").strip(),
        tz=os.getenv("TZ", "Etc/UTC").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        memory_max_turns=int(os.getenv("MEMORY_MAX_TURNS", "20").strip()),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    )
