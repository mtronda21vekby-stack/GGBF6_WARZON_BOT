# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.observability.quality import quality_telemetry
from app.webapp.security import verify_init_data

router = APIRouter()
APP_STORE: Any = None
_HASH_RE = re.compile(r"^[a-f0-9]{16,64}$")


class FeedbackBody(BaseModel):
    rating: Literal["helpful", "not_helpful"]
    response_hash: str = Field(min_length=16, max_length=64)
    surface: str = Field(default="miniapp_chat", max_length=40)


def bind_runtime(*, store=None) -> None:
    global APP_STORE
    APP_STORE = store


def _identity(meta: dict) -> int | None:
    value = meta.get("chat_id") or meta.get("user_id")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _already_recorded(chat_id: int, response_hash: str) -> bool:
    if APP_STORE is None:
        return False
    fn = getattr(APP_STORE, "list_progression_events", None)
    if not callable(fn):
        return False
    try:
        for event in list(fn(chat_id) or [])[:50]:
            if not isinstance(event, dict):
                continue
            if event.get("type") == "answer_feedback" and event.get("response_hash") == response_hash:
                return True
    except Exception:
        return False
    return False


@router.post("/webapp/api/feedback")
def submit_answer_feedback(
    body: FeedbackBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    trusted, meta = verify_init_data((x_telegram_init_data or "").strip())
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")
    chat_id = _identity(dict(meta or {}))
    if chat_id is None:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    if APP_STORE is None:
        raise HTTPException(status_code=503, detail="feedback_store_unavailable")

    response_hash = body.response_hash.lower().strip()
    if not _HASH_RE.fullmatch(response_hash):
        raise HTTPException(status_code=422, detail="invalid_response_hash")

    if _already_recorded(chat_id, response_hash):
        return {"ok": True, "duplicate": True}

    event = {
        "type": "answer_feedback",
        "rating": body.rating,
        "response_hash": response_hash,
        "surface": str(body.surface or "miniapp_chat")[:40],
        "source": "explicit_user_feedback",
        "at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        APP_STORE.add_progression_event(chat_id, event)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"feedback_store_error:{type(exc).__name__}")

    quality_telemetry.record_feedback(body.rating)
    return {"ok": True, "duplicate": False}
