# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.analytics.command_center import CommandCenterService
from app.services.missions.service import AdaptiveMissionService, MissionConflict
from app.webapp.security import verify_init_data

log = logging.getLogger("bco.command_center")
router = APIRouter()

APP_STORE: Any = None
APP_PROFILES: Any = None
APP_SETTINGS: Any = None


def bind_runtime(*, store=None, profiles=None, settings=None) -> None:
    global APP_STORE, APP_PROFILES, APP_SETTINGS
    APP_STORE = store
    APP_PROFILES = profiles
    APP_SETTINGS = settings
    log.info(
        "command center runtime bind store=%s profiles=%s settings=%s",
        bool(store),
        bool(profiles),
        bool(settings),
    )


def _identity(meta: dict) -> int | None:
    value = meta.get("chat_id") or meta.get("user_id")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _trusted_identity(init_data: str) -> tuple[int, dict[str, Any]]:
    trusted, meta = verify_init_data((init_data or "").strip())
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")

    safe_meta = dict(meta or {})
    chat_id = _identity(safe_meta)
    if chat_id is None:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    if APP_STORE is None or APP_PROFILES is None:
        raise HTTPException(status_code=503, detail="command_center_unavailable")
    return chat_id, safe_meta


def _mission_service() -> AdaptiveMissionService:
    enabled = (
        bool(getattr(APP_SETTINGS, "adaptive_mission_control_enabled", True))
        if APP_SETTINGS is not None
        else True
    )
    return AdaptiveMissionService(
        store=APP_STORE,
        profiles=APP_PROFILES,
        enabled=enabled,
    )


def _response(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _snapshot_response(init_data: str):
    chat_id, _ = _trusted_identity(init_data)
    snapshot = CommandCenterService(store=APP_STORE, profiles=APP_PROFILES).snapshot(chat_id)
    mission = _mission_service().snapshot(chat_id)
    return _response({
        "ok": True,
        "trusted": True,
        "player": snapshot,
        "mission_control": mission,
    })


class MissionAcceptBody(BaseModel):
    mission_id: str = Field(min_length=5, max_length=48)


class MissionCompleteBody(BaseModel):
    mission_id: str = Field(min_length=5, max_length=48)
    outcome: str = Field(default="reported", max_length=32)
    metrics: dict[str, Any] = Field(default_factory=dict)


@router.get("/webapp/api/intelligence")
def command_center_intelligence_get(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    return _snapshot_response(x_telegram_init_data or "")


@router.post("/webapp/api/intelligence")
def command_center_intelligence_post(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    return _snapshot_response(x_telegram_init_data or "")


@router.get("/webapp/api/mission")
def adaptive_mission_get(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    chat_id, _ = _trusted_identity(x_telegram_init_data or "")
    return _response({
        "ok": True,
        "trusted": True,
        "mission_control": _mission_service().snapshot(chat_id),
    })


@router.post("/webapp/api/mission/accept")
def adaptive_mission_accept(
    body: MissionAcceptBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    chat_id, _ = _trusted_identity(x_telegram_init_data or "")
    try:
        snapshot = _mission_service().accept(chat_id, body.mission_id)
    except MissionConflict as exc:
        return _response(
            {"ok": False, "error": str(exc), "mission_control": _mission_service().snapshot(chat_id)},
            status_code=409,
        )
    return _response({"ok": True, "trusted": True, "mission_control": snapshot})


@router.post("/webapp/api/mission/complete")
def adaptive_mission_complete(
    body: MissionCompleteBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    chat_id, _ = _trusted_identity(x_telegram_init_data or "")
    try:
        snapshot = _mission_service().complete(
            chat_id,
            body.mission_id,
            outcome=body.outcome,
            metrics=body.metrics,
        )
    except MissionConflict as exc:
        return _response(
            {"ok": False, "error": str(exc), "mission_control": _mission_service().snapshot(chat_id)},
            status_code=409,
        )
    return _response({"ok": True, "trusted": True, "mission_control": snapshot})
