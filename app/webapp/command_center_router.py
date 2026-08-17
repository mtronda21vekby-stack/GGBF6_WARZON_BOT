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
from app.services.operator_intelligence.adaptive_strategy import PremiumAdaptiveStrategyService
from app.services.operator_intelligence.deep_history import PremiumDeepHistoryService
from app.services.operator_intelligence.strategy_outcomes import PremiumStrategyOutcomeService
from app.services.operator_intelligence.strategy_portfolio import StrategyPortfolioCalibration
from app.webapp.security import verify_init_data

log = logging.getLogger("bco.command_center")
router = APIRouter()

APP_STORE: Any = None
APP_PROFILES: Any = None
APP_ENTITLEMENTS: Any = None


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


def bind_runtime(*, store=None, profiles=None, entitlements=None) -> None:
    global APP_STORE, APP_PROFILES, APP_ENTITLEMENTS
    APP_STORE = store
    APP_PROFILES = profiles
    APP_ENTITLEMENTS = entitlements
    log.info(
        "command center runtime bind store=%s profiles=%s entitlements=%s",
        bool(store), bool(profiles), bool(entitlements),
    )


def _identity(meta: dict) -> int | None:
    value = meta.get("chat_id") or meta.get("user_id")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _trusted_meta(init_data: str) -> tuple[int, int, dict[str, Any]]:
    trusted, raw_meta = verify_init_data((init_data or "").strip())
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")
    meta = dict(raw_meta or {})
    chat_id = _identity(meta)
    try:
        user_id = int(meta.get("user_id"))
    except Exception:
        user_id = None
    if chat_id is None or user_id is None or user_id <= 0:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    if APP_STORE is None or APP_PROFILES is None:
        raise HTTPException(status_code=503, detail="command_center_unavailable")
    return chat_id, user_id, meta


def _trusted_identity(init_data: str) -> int:
    chat_id, _, _ = _trusted_meta(init_data)
    return chat_id


async def _require_premium(init_data: str, *, feature: str) -> tuple[int, int]:
    """Resolve Premium from the shared server authority; never from client state."""
    chat_id, user_id, _ = _trusted_meta(init_data)
    if APP_ENTITLEMENTS is None:
        raise HTTPException(status_code=503, detail="premium_authority_unavailable")
    try:
        status = await APP_ENTITLEMENTS.get_status(user_id)
    except Exception as exc:
        log.warning("%s entitlement check failed user_id=%s error=%s", feature, user_id, type(exc).__name__)
        raise HTTPException(status_code=503, detail="premium_authority_unavailable")
    entitlements = tuple(getattr(status, "entitlements", ()) or ())
    if not bool(getattr(status, "premium", False)) or "bco_premium" not in entitlements:
        raise HTTPException(status_code=403, detail="bco_premium_required")
    return chat_id, user_id


def _operator_service() -> OperatorIntelligenceService:
    if APP_STORE is None or APP_PROFILES is None:
        raise HTTPException(status_code=503, detail="operator_intelligence_unavailable")
    return OperatorIntelligenceService(
        store=APP_STORE,
        profiles=APP_PROFILES,
        operator_enabled=_env_on("OPERATOR_INTELLIGENCE_ENABLED"),
        missions_enabled=_env_on("ADAPTIVE_MISSION_CONTROL_ENABLED"),
    )


def _no_store(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
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


@router.get("/webapp/api/operator-deep-history")
async def operator_deep_history_get(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    if not _env_on("PREMIUM_DEEP_HISTORY_ENABLED"):
        raise HTTPException(status_code=503, detail="premium_deep_history_disabled")
    chat_id, _ = await _require_premium(x_telegram_init_data or "", feature="deep_history")
    data = PremiumDeepHistoryService(APP_STORE).snapshot(chat_id)
    return _no_store({"ok": True, "trusted": True, "premium": True, "premium_authority": "server_bco_premium", "data": data})


@router.get("/webapp/api/operator-strategy")
async def operator_strategy_get(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    if not _env_on("PREMIUM_ADAPTIVE_STRATEGY_ENABLED"):
        raise HTTPException(status_code=503, detail="premium_adaptive_strategy_disabled")
    chat_id, _ = await _require_premium(x_telegram_init_data or "", feature="adaptive_strategy")
    deep_history = PremiumDeepHistoryService(APP_STORE).snapshot(chat_id)
    operator = _operator_service().snapshot(chat_id)
    outcome_loop = PremiumStrategyOutcomeService(APP_STORE)
    prior_effectiveness = outcome_loop.snapshot(chat_id)
    portfolio = StrategyPortfolioCalibration.snapshot(prior_effectiveness)
    data = PremiumAdaptiveStrategyService().build(deep_history, operator, portfolio)
    strategy_id = outcome_loop.record_issue(chat_id, data)
    effectiveness = outcome_loop.snapshot(chat_id)
    data = dict(data)
    data["strategy_id"] = strategy_id
    data["effectiveness"] = effectiveness
    data["strategy_portfolio"] = portfolio
    return _no_store({
        "ok": True,
        "trusted": True,
        "premium": True,
        "premium_authority": "server_bco_premium",
        "strategy_authority": "evidence_driven_recommendation",
        "effectiveness_authority": "explicit_outcome_association_only",
        "portfolio_authority": "associative_outcome_calibration_only",
        "data": data,
    })


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
        data = _operator_service().complete(chat_id, body.mission_id, outcome=body.outcome, metrics=body.metrics)
    except MissionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _no_store({"ok": True, "trusted": True, "data": data})
