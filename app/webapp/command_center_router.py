# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from app.services.analytics.command_center import CommandCenterService
from app.webapp.security import verify_init_data

log = logging.getLogger("bco.command_center")
router = APIRouter()

APP_STORE: Any = None
APP_PROFILES: Any = None


def bind_runtime(*, store=None, profiles=None) -> None:
    global APP_STORE, APP_PROFILES
    APP_STORE = store
    APP_PROFILES = profiles
    log.info("command center runtime bind store=%s profiles=%s", bool(store), bool(profiles))


def _identity(meta: dict) -> int | None:
    value = meta.get("chat_id") or meta.get("user_id")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


@router.post("/webapp/api/intelligence")
def command_center_intelligence(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    trusted, meta = verify_init_data((x_telegram_init_data or "").strip())
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")

    chat_id = _identity(dict(meta or {}))
    if chat_id is None:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    if APP_STORE is None or APP_PROFILES is None:
        raise HTTPException(status_code=503, detail="command_center_unavailable")

    snapshot = CommandCenterService(store=APP_STORE, profiles=APP_PROFILES).snapshot(chat_id)
    return JSONResponse(
        {"ok": True, "trusted": True, "player": snapshot},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
