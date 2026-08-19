# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import KnowledgeRequest
from app.services.brain.live_official import OfficialPatchKnowledgeProvider
from app.services.crown_session import CrownSessionService
from app.services.session_cycle import CrownSessionCycleService


_OFFICIAL = OfficialPatchKnowledgeProvider(ttl_s=900, timeout_s=6.0)


class SessionBriefingService:
    """Build a pre-session briefing from trusted player state + official current-game evidence."""

    def __init__(self, *, store: Any, profiles: Any, entitlements: Any = None) -> None:
        self.store = store
        self.profiles = profiles
        self.entitlements = entitlements

    @staticmethod
    def _official_payload(ctx) -> dict[str, Any]:
        facts = []
        for fact in list(getattr(ctx, "facts", []) or [])[:8]:
            text = str(getattr(fact, "text", "") or "").strip()
            if text:
                facts.append(text[:600])
        return {
            "confidence": str(getattr(getattr(ctx, "confidence", None), "value", "UNKNOWN")),
            "source": str(getattr(ctx, "source", "") or "")[:500] or None,
            "last_updated": str(getattr(ctx, "last_updated", "") or "")[:64] or None,
            "freshness": str(getattr(ctx, "freshness", "") or "unknown")[:160],
            "facts": facts,
        }

    @staticmethod
    def _focus(session: dict[str, Any]) -> list[str]:
        meta = dict(session.get("personal_meta") or {})
        mission = dict(session.get("mission") or session.get("next_mission") or {})
        out: list[str] = []
        objective = str(mission.get("objective") or "").strip()
        if objective:
            out.append(objective[:280])
        for item in list(meta.get("top_mistakes") or [])[:2]:
            if isinstance(item, dict):
                label = str(item.get("label") or "").strip()
                if label:
                    out.append(f"Avoid recurring pattern: {label}"[:280])
        if not out:
            out.append("Collect clean evidence before changing strategy.")
        return out[:3]

    async def prepare(self, *, chat_id: int, telegram_user_id: int) -> dict[str, Any]:
        session = await CrownSessionService(
            store=self.store,
            profiles=self.profiles,
            entitlements=self.entitlements,
        ).snapshot(chat_id=int(chat_id), telegram_user_id=int(telegram_user_id))

        profile = dict(session.get("profile") or {})
        game = str(profile.get("game") or "Warzone")[:40]
        mission = dict(session.get("mission") or session.get("next_mission") or {})
        cycle = CrownSessionCycleService(self.store).start(int(chat_id), mission)

        request = KnowledgeRequest(
            intent=IntentResult(Intent.PATCH_CURRENT, 1.0, needs_current_data=True, reason="prepare_session"),
            text=f"latest official patch changes relevant to {game} session preparation",
            profile=profile,
        )
        official = await asyncio.to_thread(_OFFICIAL.query, request)
        official_payload = self._official_payload(official)
        entitlement = dict(session.get("entitlement") or {})

        return {
            "schema": "crown-war-room-briefing-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "crown_session": {
                "id": cycle.get("crown_session_id"),
                "status": "prepared",
                "mission_id": cycle.get("mission_id"),
                "prepared_at": cycle.get("at"),
                "authority": "server_progression_event",
            },
            "identity": session.get("identity") or {},
            "world": {
                "game": game,
                "mode": profile.get("mode"),
                "input": profile.get("input"),
                "platform": profile.get("platform"),
                "brain_mode": profile.get("difficulty"),
            },
            "operator_state": session.get("operator_twin") or {},
            "personal_meta": session.get("personal_meta") or {},
            "mission": mission,
            "session_focus": self._focus(session),
            "official_intel": official_payload,
            "squad_context": {
                "status": "UNKNOWN",
                "authority": "no_trusted_squad_source",
                "members": [],
            },
            "access": {
                "premium": entitlement.get("premium") is True,
                "authority": entitlement.get("authority") or "server",
                "state": entitlement.get("state") or "unavailable",
            },
            "truth": {
                "official_patch_facts_only": True,
                "official_meta_ranking_claimed": False,
                "unknown_squad_not_inferred": True,
                "mission_authority": "operator_intelligence",
                "session_cycle_persisted": True,
            },
        }
