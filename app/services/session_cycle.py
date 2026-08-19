# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

EVENT_TYPE = "crown_session_cycle"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(store: Any, chat_id: int) -> list[dict[str, Any]]:
    fn = getattr(store, "list_progression_events", None)
    if not callable(fn):
        return []
    try:
        raw = fn(int(chat_id), 160)
    except TypeError:
        raw = fn(int(chat_id))
    except Exception:
        return []
    return [dict(x) for x in list(raw or []) if isinstance(x, Mapping)]


class CrownSessionCycleService:
    """Persist one server-owned session cycle across PREPARE, VOD and AFTER ACTION."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def current(self, chat_id: int, mission_id: str | None = None) -> dict[str, Any] | None:
        wanted = str(mission_id or "").strip()
        rows = _rows(self.store, int(chat_id))
        closed = {
            str(x.get("crown_session_id") or "")
            for x in rows
            if str(x.get("type") or "") == EVENT_TYPE and str(x.get("status") or "") == "closed"
        }
        candidates = [
            x for x in rows
            if str(x.get("type") or "") == EVENT_TYPE
            and str(x.get("status") or "") == "prepared"
            and str(x.get("crown_session_id") or "") not in closed
            and (not wanted or str(x.get("mission_id") or "") == wanted)
        ]
        candidates.sort(key=lambda x: str(x.get("at") or x.get("created_at") or ""), reverse=True)
        return dict(candidates[0]) if candidates else None

    def start(self, chat_id: int, mission: Mapping[str, Any] | None) -> dict[str, Any]:
        mission = dict(mission or {})
        mission_id = str(mission.get("id") or "calibration")[:64]
        existing = self.current(int(chat_id), mission_id)
        if existing:
            return existing
        at = _now_iso()
        raw = f"{int(chat_id)}:{mission_id}:{at}"
        session_id = "crown_sess_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
        event = {
            "type": EVENT_TYPE,
            "status": "prepared",
            "crown_session_id": session_id,
            "mission_id": mission_id,
            "mission_title": str(mission.get("title") or "")[:140],
            "focus": str(mission.get("focus") or "")[:40],
            "source": "crown_session_prepare",
            "at": at,
        }
        fn = getattr(self.store, "add_progression_event", None)
        if callable(fn):
            fn(int(chat_id), event)
        return event

    def close(self, chat_id: int, crown_session_id: str, mission_id: str, outcome: str) -> dict[str, Any] | None:
        sid = str(crown_session_id or "").strip()
        if not sid:
            return None
        event = {
            "type": EVENT_TYPE,
            "status": "closed",
            "crown_session_id": sid[:64],
            "mission_id": str(mission_id or "")[:64],
            "outcome": str(outcome or "reported")[:32],
            "source": "crown_after_action",
            "at": _now_iso(),
        }
        fn = getattr(self.store, "add_progression_event", None)
        if callable(fn):
            fn(int(chat_id), event)
            return event
        return None
