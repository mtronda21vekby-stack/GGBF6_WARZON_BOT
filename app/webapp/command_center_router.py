# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.analytics.command_center import CommandCenterService
from app.services.operator_intelligence import MissionConflict, OperatorIntelligenceService
from app.webapp.security import verify_init_data

log = logging.getLogger("bco.command_center")
router = APIRouter()

APP_STORE: Any = None
APP_PROFILES: Any = None


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


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


def _trusted_identity(init_data: str) -> int:
    trusted, meta = verify_init_data((init_data or "").strip())
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")
    chat_id = _identity(dict(meta or {}))
    if chat_id is None:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    if APP_STORE is None or APP_PROFILES is None:
        raise HTTPException(status_code=503, detail="command_center_unavailable")
    return chat_id


def _operator_service() -> OperatorIntelligenceService:
    if APP_STORE is None or APP_PROFILES is None:
        raise HTTPException(status_code=503, detail="operator_intelligence_unavailable")
    return OperatorIntelligenceService(
        store=APP_STORE,
        profiles=APP_PROFILES,
        operator_enabled=_env_on("OPERATOR_INTELLIGENCE_ENABLED"),
        missions_enabled=_env_on("ADAPTIVE_MISSION_CONTROL_ENABLED"),
    )


def _no_store(payload: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        payload,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


def _snapshot_response(init_data: str):
    chat_id = _trusted_identity(init_data)
    snapshot = CommandCenterService(store=APP_STORE, profiles=APP_PROFILES).snapshot(chat_id)
    operator = _operator_service().snapshot(chat_id)
    return _no_store({"ok": True, "trusted": True, "player": snapshot, "operator_intelligence": operator})


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


@router.get("/webapp/api/operator-intelligence")
def operator_intelligence_get(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    chat_id = _trusted_identity(x_telegram_init_data or "")
    return _no_store({"ok": True, "trusted": True, "data": _operator_service().snapshot(chat_id)})


class MissionAcceptBody(BaseModel):
    mission_id: str = Field(default="", min_length=1, max_length=64)


class MissionCompleteBody(BaseModel):
    mission_id: str = Field(default="", min_length=1, max_length=64)
    outcome: str = Field(default="reported", max_length=32)
    metrics: dict[str, Any] = Field(default_factory=dict)


@router.post("/webapp/api/operator-mission/accept")
def operator_mission_accept(
    body: MissionAcceptBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    chat_id = _trusted_identity(x_telegram_init_data or "")
    try:
        data = _operator_service().accept(chat_id, body.mission_id)
    except MissionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _no_store({"ok": True, "trusted": True, "data": data})


@router.post("/webapp/api/operator-mission/complete")
def operator_mission_complete(
    body: MissionCompleteBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    chat_id = _trusted_identity(x_telegram_init_data or "")
    try:
        data = _operator_service().complete(
            chat_id,
            body.mission_id,
            outcome=body.outcome,
            metrics=body.metrics,
        )
    except MissionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _no_store({"ok": True, "trusted": True, "data": data})
