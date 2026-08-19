# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


EVENT_TYPE = "vod_engagement_intelligence"
SOURCE = "vision_sampled_frames"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 280) -> str:
    return " ".join(str(value or "").split())[:limit]


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except Exception:
        return 0.0


@dataclass
class VODEngagementIntelligenceService:
    store: Any

    def build(self, *, chat_id: int, result: Any, crown_session_id: str | None, mission_id: str | None) -> dict[str, Any] | None:
        timeline = list(getattr(result, "timeline", []) or [])[:24]
        if not timeline:
            return None

        engagements: list[dict[str, Any]] = []
        for idx, item in enumerate(timeline, start=1):
            confidence = _confidence(getattr(item, "confidence", 0.0))
            timestamp = _clean(getattr(item, "timestamp", ""), 32)
            observation = _clean(getattr(item, "observation", ""), 420)
            decision = _clean(getattr(item, "decision", ""), 320)
            issue = _clean(getattr(item, "issue", ""), 320)
            correction = _clean(getattr(item, "correction", ""), 360)
            category = _clean(getattr(item, "category", "unknown"), 32) or "unknown"
            if not any((observation, decision, issue, correction)):
                continue
            engagements.append({
                "engagement_id": f"eng_{idx:02d}",
                "timestamp": timestamp or None,
                "entry": observation or None,
                "first_damage": None,
                "position": observation if category in {"positioning", "awareness"} else None,
                "decision": decision or None,
                "result": issue or None,
                "correction": correction or None,
                "category": category,
                "confidence": round(confidence, 3),
                "sampled_frame_only": True,
                "continuous_sequence_claimed": False,
            })
            if len(engagements) >= 12:
                break

        if not engagements:
            return None

        event = {
            "type": EVENT_TYPE,
            "status": "observed",
            "source": SOURCE,
            "crown_session_id": _clean(crown_session_id, 96) or None,
            "mission_id": _clean(mission_id, 64) or None,
            "engagement_count": len(engagements),
            "engagements": engagements,
            "limitations": _clean(getattr(result, "limitations", ""), 500),
            "truth_contract": {
                "sampled_frames_only": True,
                "continuous_video_claimed": False,
                "first_damage_unknown_unless_explicitly_visible": True,
                "mission_auto_complete": False,
            },
            "at": _now_iso(),
        }

        add = getattr(self.store, "add_progression_event", None)
        if callable(add):
            try:
                add(int(chat_id), event)
            except Exception:
                return None
        else:
            return None

        add_episode = getattr(self.store, "add_episode", None)
        if callable(add_episode):
            try:
                add_episode(int(chat_id), {"kind": EVENT_TYPE, **{k: v for k, v in event.items() if k != "type"}})
            except Exception:
                pass
        return event
