# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.brain.intents import Intent, classify_intent
from app.services.player_memory.analytics import PlayerAnalytics
from app.services.player_memory.extractor import extract_player_memory
from app.services.session_cycle import CrownSessionCycleService
from app.services.vod.engagements import VODEngagementIntelligenceService
from app.services.vod.mission_evidence import MissionEvidenceFusionService


_SIGNIFICANT_INTENTS = {
    Intent.GAME_TACTICS, Intent.DEATH_ANALYSIS, Intent.POSITIONING, Intent.AIM,
    Intent.MOVEMENT, Intent.LOADOUT, Intent.TRAINING, Intent.VOD_TEXT_ANALYSIS,
    Intent.PLAYER_PROGRESS,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlayerMemoryService:
    store: Any
    profiles: Any

    def __post_init__(self) -> None:
        self.analytics = PlayerAnalytics(self.store)

    def context(self, chat_id: int, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        base = dict(profile or {})
        try: summary = str(self.store.get_summary(chat_id) or "")
        except Exception: summary = ""
        try: mistakes = list(self.store.list_mistake_stats(chat_id) or [])[:5]
        except Exception: mistakes = []
        try: training = list(self.store.list_training_sessions(chat_id) or [])[:3]
        except Exception: training = []
        try: progression = list(self.store.list_progression_events(chat_id) or [])[:5]
        except Exception: progression = []
        try: derived = dict(self.store.get_derived_intelligence(chat_id) or {})
        except Exception: derived = {}
        base.update({
            "memory_summary": summary,
            "top_mistakes": [{"label": x.get("label"), "count": x.get("count", 1)} for x in mistakes if x.get("label")],
            "recent_training": training,
            "recent_progression": progression,
            "derived_intelligence": derived,
        })
        return base

    def _build_summary(self, chat_id: int, profile: dict[str, Any], snapshot: dict[str, Any]) -> str:
        parts: list[str] = []
        goal = profile.get("current_goal")
        if goal: parts.append(f"Цель: {goal}")
        top = snapshot.get("top_mistakes") or []
        if top:
            parts.append("Повторяющиеся ошибки: " + ", ".join(f"{x['label']} ×{x['count']}" for x in top[:3]))
        trends = snapshot.get("trends") or {}
        if trends:
            trend_bits = [f"{key} Δ{value.get('delta', 0):+g}" for key, value in trends.items()]
            if trend_bits: parts.append("Тренды: " + ", ".join(trend_bits))
        return ". ".join(parts)[:1000]

    def _refresh_derived(self, chat_id: int, fallback_profile: dict[str, Any]) -> None:
        try: latest_profile = self.profiles.get(chat_id)
        except Exception: latest_profile = dict(fallback_profile or {})
        snapshot = self.analytics.snapshot(chat_id)
        try:
            self.store.set_derived_intelligence(chat_id, snapshot)
            self.store.set_summary(chat_id, self._build_summary(chat_id, latest_profile, snapshot))
        except Exception:
            pass

    def observe(self, *, chat_id: int, text: str, profile: dict[str, Any], reply: str = "", trusted: bool = True) -> None:
        if not trusted: return
        cid = int(chat_id)
        intent = classify_intent(text, profile)
        extracted = extract_player_memory(text)
        if extracted.profile_patch:
            try: self.profiles.patch(cid, extracted.profile_patch)
            except Exception: pass
        for mistake in extracted.mistakes:
            try: self.store.add_recurring_mistake(cid, mistake)
            except Exception: pass
        if intent.intent in _SIGNIFICANT_INTENTS or extracted.metrics or extracted.profile_patch or extracted.mistakes:
            try:
                self.store.add_episode(cid, {"kind": "conversation_signal", "intent": intent.intent.value, "game": profile.get("game"), "note": str(text or "")[:500], "metrics": extracted.metrics, "mistakes": extracted.mistakes, "at": _now_iso()})
            except Exception: pass
        if extracted.metrics:
            try: self.store.add_progression_event(cid, {"type": "match_report", "game": profile.get("game"), "metrics": extracted.metrics, "source": "explicit_user_report", "at": _now_iso()})
            except Exception: pass
            try: self.profiles.patch(cid, {"last_session_summary": f"Явный отчёт игрока: {extracted.metrics}"})
            except Exception: pass
        if intent.intent == Intent.TRAINING:
            focus = "hybrid"; low = str(text or "").lower()
            if "аим" in low or "aim" in low: focus = "aim"
            elif "мув" in low or "movement" in low: focus = "movement"
            elif "пози" in low or "ротац" in low: focus = "positioning"
            try:
                self.store.add_training_session(cid, {"focus": focus, "game": profile.get("game"), "source": "conversation", "at": _now_iso()})
                self.profiles.patch(cid, {"training_focus": focus})
            except Exception: pass
        self._refresh_derived(cid, profile)

    def observe_vod(self, *, chat_id: int, profile: dict[str, Any], result: Any, trusted: bool = True) -> dict[str, Any] | None:
        """Persist sampled-frame evidence with the current server-owned CROWN SESSION context."""
        if not trusted: return None
        cid = int(chat_id)
        cycle = CrownSessionCycleService(self.store).current(cid)
        context = {
            "crown_session_id": str((cycle or {}).get("crown_session_id") or "")[:64] or None,
            "mission_id": str((cycle or {}).get("mission_id") or "")[:64] or None,
        }
        payload = {}
        if hasattr(result, "memory_payload") and callable(result.memory_payload):
            try: payload = dict(result.memory_payload() or {})
            except Exception: payload = {}

        high_conf_labels: list[str] = []
        for item in list(getattr(result, "mistakes", []) or []):
            label = str(getattr(item, "label", "") or "").strip()
            try: confidence = float(getattr(item, "confidence", 0.0) or 0.0)
            except Exception: confidence = 0.0
            if label and confidence >= 0.65:
                high_conf_labels.append(label)
                try: self.store.add_recurring_mistake(cid, label)
                except Exception: pass

        try:
            self.store.add_episode(cid, {
                "kind": "vod_sampled_frames", "game": profile.get("game"), "source": "vision_sampled_frames",
                **context, "analysis": payload, "confirmed_mistakes": high_conf_labels[:8], "at": _now_iso(),
            })
        except Exception: pass
        try:
            self.store.add_progression_event(cid, {
                "type": "vod_review", "game": profile.get("game"), "source": "vision_sampled_frames", **context,
                "sampled_frames": len(getattr(result, "sampled_timestamps", []) or []),
                "high_confidence_mistakes": len(high_conf_labels), "at": _now_iso(),
            })
        except Exception: pass

        try: fusion_event = MissionEvidenceFusionService(store=self.store).correlate_vod(cid, result)
        except Exception: fusion_event = None
        try:
            VODEngagementIntelligenceService(store=self.store).build(
                chat_id=cid,
                result=result,
                crown_session_id=context["crown_session_id"],
                mission_id=context["mission_id"],
            )
        except Exception:
            pass

        summary = str(getattr(result, "summary", "") or "").strip()
        next_drill = str(getattr(result, "next_drill", "") or "").strip()
        patch: dict[str, Any] = {}
        if summary: patch["last_session_summary"] = f"VOD sampled-frames: {summary[:700]}"
        if next_drill: patch["training_focus"] = next_drill[:400]
        if patch:
            try: self.profiles.patch(cid, patch)
            except Exception: pass
        self._refresh_derived(cid, profile)
        return fusion_event
