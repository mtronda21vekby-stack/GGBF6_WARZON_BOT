# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.services.analytics.command_center import CommandCenterService
from app.services.identity import CrownIdentityCore
from app.services.operator_intelligence.orchestrated_service import OrchestratedOperatorIntelligenceService


class CrownSessionService:
    """Compose one trusted, read-only player session for every BLACK CROWN surface.

    Legacy gameplay memory remains keyed by Telegram chat_id during the migration
    window. The canonical black_crown_user_id is projected alongside it and is
    the durable account identity for Website, Telegram Bot and Mini App.
    """

    def __init__(self, *, store: Any, profiles: Any, entitlements: Any = None) -> None:
        self.store = store
        self.profiles = profiles
        self.entitlements = entitlements

    @staticmethod
    def _public_entitlement(status: Any) -> dict[str, Any]:
        if status is None:
            return {"linked": False, "premium": False, "entitlements": []}
        raw = asdict(status) if is_dataclass(status) else dict(status) if isinstance(status, Mapping) else {}
        return {
            "linked": raw.get("linked") is True,
            "premium": raw.get("premium") is True,
            "entitlements": [str(x) for x in list(raw.get("entitlements") or [])[:100]],
            "linked_at": str(raw.get("linked_at") or "")[:64] or None,
        }

    async def snapshot(self, *, chat_id: int, telegram_user_id: int) -> dict[str, Any]:
        cid = int(chat_id)
        uid = int(telegram_user_id)
        identity = CrownIdentityCore(self.store).resolve_telegram(uid)
        profile = dict(self.profiles.get(cid) or {})
        player = CommandCenterService(store=self.store, profiles=self.profiles).snapshot(cid)
        operator = OrchestratedOperatorIntelligenceService.from_components(
            store=self.store,
            profiles=self.profiles,
        ).snapshot(cid)

        entitlement_status = None
        entitlement_state = "unavailable"
        if self.entitlements is not None:
            try:
                entitlement_status = await self.entitlements.get_status(uid)
                entitlement_state = "resolved"
            except Exception:
                entitlement_state = "unavailable"

        canonical_id = identity.black_crown_user_id if identity is not None else str(profile.get("_black_crown_user_id") or "") or None
        identity_status = identity.status if identity is not None else str(profile.get("_identity_status") or "") or None
        account_status = identity.account_status if identity is not None else str(profile.get("_account_status") or "") or None

        return {
            "schema": "crown-session-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "identity": {
                "black_crown_user_id": canonical_id,
                "provider": "telegram",
                "status": identity_status,
                "account_status": account_status,
                "canonical": bool(canonical_id),
            },
            "profile": player.get("profile") or {},
            "player": player,
            "operator_twin": operator,
            "mission": operator.get("mission"),
            "next_mission": operator.get("next_mission"),
            "personal_meta": {
                "summary": player.get("summary") or "",
                "scores": player.get("scores") or {},
                "coverage": player.get("coverage") or 0,
                "top_mistakes": player.get("top_mistakes") or [],
                "trends": player.get("trends") or {},
            },
            "entitlement": {
                "authority": "server",
                "state": entitlement_state,
                **self._public_entitlement(entitlement_status),
            },
        }
