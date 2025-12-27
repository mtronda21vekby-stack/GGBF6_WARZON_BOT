# app/config.py
from __future__ import annotations

import os
from dataclasses import dataclass


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"{name} is required")
    return v


@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str
    WEBHOOK_SECRET: str
    WEBHOOK_PATH: str
    PUBLIC_URL: str


def get_settings() -> Settings:
    secret = _req("WEBHOOK_SECRET")
    path = os.getenv("WEBHOOK_PATH", f"/telegram/webhook/{secret}").strip()
    if not path.startswith("/"):
        path = "/" + path

    return Settings(
        BOT_TOKEN=_req("BOT_TOKEN"),
        WEBHOOK_SECRET=secret,
        WEBHOOK_PATH=path,
        PUBLIC_URL=_req("PUBLIC_URL").rstrip("/"),
    )
