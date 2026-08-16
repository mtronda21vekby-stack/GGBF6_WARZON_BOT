# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.brain.intents import Intent, classify_intent
from app.services.player_memory.analytics import PlayerAnalytics
from app.services.player_memory.extractor import extract_player_memory


_SIGNIFICANT_INTENTS = {
    Intent.GAME_TACTICS,
    Intent.DEATH_ANALYSIS,
    Intent.POSITIONING,
    Intent.AIM,
    Intent.MOVEMENT,
    Intent.LOADOUT,
    Intent.TRAINING,
    Intent.VOD_TEXT_ANALYSIS,
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
        try:
            summary = str(self.store.get_summary(chat_id) or "")
        except Exception:
            summary = ""
        try:
            mistakes = list(self.store.list_mistake_stats(chat_id) or [])[:5]
        except Exception:
            mistakes = []
        try:
            training = list(self.store.list_training_sessions(chat_id) or [])[:3]
        except Exception:
            training = []
        try:
            progression = list(self.store.list_progression_events(chat_id) or [])[:5]
        except Exception:
            progression = []
        try:
            derived = dict(self.store.get_derived_intelligence(chat_id) or {})
        except Exception:
            derived = {}

        base.update({
            "memory_summary": summary,
            "top_mistakes": [
                {"label": x.get("label"), "count": x.get("count", 1)}
                for x in mistakes if x.get("label")
            ],
            "recent_training": training,
            "recent_progression": progression,
            "derived_intelligence": derived,
        })
        return base

    def _build_summary(self, chat_id: int, profile: dict[str, Any], snapshot: dict[str, Any]) -> str:
        parts: list[str] = []
        goal = profile.get("current_goal")
        if goal:
            parts.append(f"Цель: {goal}")
        top = snapshot.get("top_mistakes") or []
        if top:
            rendered = ", ".join(f"{x['label']} ×{x['count']}" for x in top[:3])
            parts.append(f"Повторяющиеся ошибки: {rendered}")
        trends = snapshot.get("trends") or {}
        if trends:
            trend_bits = []
            for key, value in trends.items():
                trend_bits.append(f"{key} Δ{value.get('delta', 0):+g}")
            if trend_bits:
                parts.append("Тренды: " + ", ".join(trend_bits))
        return ". ".join(parts)[:1000]

    def observe(self, *, chat_id: int, text: str, profile: dict[str, Any], reply: str = "", trusted: bool = True) -> None:
        """Persist only evidence-backed long-term intelligence.

        No additional LLM call is made. Untrusted Mini App requests must pass
        trusted=False and are ignored for persistent mutation.
        """
        if not trusted:
            return
        cid = int(chat_id)
        intent = classify_intent(text, profile)
        extracted = extract_player_memory(text)

        if extracted.profile_patch:
            try:
                self.profiles.patch(cid, extracted.profile_patch)
            except Exception:
                pass

        for mistake in extracted.mistakes:
            try:
                self.store.add_recurring_mistake(cid, mistake)
            except Exception:
                pass

        if intent.intent in _SIGNIFICANT_INTENTS or extracted.metrics or extracted.profile_patch or extracted.mistakes:
            try:
                self.store.add_episode(cid, {
                    "kind": "conversation_signal",
                    "intent": intent.intent.value,
                    "game": profile.get("game"),
                    "note": str(text or "")[:500],
                    "metrics": extracted.metrics,
                    "mistakes": extracted.mistakes,
                    "at": _now_iso(),
                })
            except Exception:
                pass

        if extracted.metrics:
            event = {
                "type": "match_report",
                "game": profile.get("game"),
                "metrics": extracted.metrics,
                "source": "explicit_user_report",
                "at": _now_iso(),
            }
            try:
                self.store.add_progression_event(cid, event)
            except Exception:
                pass
            try:
                self.profiles.patch(cid, {"last_session_summary": f"Явный отчёт игрока: {extracted.metrics}"})
            except Exception:
                pass

        if intent.intent == Intent.TRAINING:
            focus = "hybrid"
            low = str(text or "").lower()
            if "аим" in low or "aim" in low:
                focus = "aim"
            elif "мув" in low or "movement" in low:
                focus = "movement"
            elif "пози" in low or "ротац" in low:
                focus = "positioning"
            try:
                self.store.add_training_session(cid, {
                    "focus": focus,
                    "game": profile.get("game"),
                    "source": "conversation",
                    "at": _now_iso(),
                })
                self.profiles.patch(cid, {"training_focus": focus})
            except Exception:
                pass

        try:
            latest_profile = self.profiles.get(cid)
        except Exception:
            latest_profile = dict(profile or {})
        snapshot = self.analytics.snapshot(cid)
        try:
            self.store.set_derived_intelligence(cid, snapshot)
            self.store.set_summary(cid, self._build_summary(cid, latest_profile, snapshot))
        except Exception:
            pass
