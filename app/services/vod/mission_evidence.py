# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


EVENT_TYPE = "operator_mission_evidence"
SOURCE = "vision_sampled_frames"

_FOCUS_RULES = {
    "aim": {
        "categories": {"aim"},
        "keywords": ("aim", "accuracy", "прицел", "recoil", "отдач", "tracking", "трекинг", "crosshair", "кроссхейр"),
    },
    "movement": {
        "categories": {"movement"},
        "keywords": ("movement", "slide", "слайд", "strafe", "стрейф", "jump", "прыж", "exit", "мув"),
    },
    "positioning": {
        "categories": {"positioning", "awareness"},
        "keywords": ("position", "пози", "cover", "укрыт", "angle", "угол", "height", "высот", "exposed", "open field"),
    },
    "rotations": {
        "categories": {"positioning", "awareness", "decision"},
        "keywords": ("rotation", "rotate", "ротац", "zone", "зон", "gas", "газ", "circle", "круг", "timing", "тайминг", "late"),
    },
    "decision": {
        "categories": {"decision", "utility", "awareness"},
        "keywords": ("decision", "решен", "engage", "reset", "ресет", "push", "пуш", "trade", "timing", "тайминг"),
    },
    "aggression": {
        "categories": {"decision", "positioning"},
        "keywords": ("aggression", "агресс", "greed", "жад", "chase", "догон", "overpush", "перепуш", "passive", "пассив"),
    },
    "survivability": {
        "categories": {"decision", "positioning", "awareness"},
        "keywords": ("surviv", "выжива", "death", "смерт", "escape", "выход", "disengage", "third party", "газ"),
    },
    "comms": {
        "categories": set(),
        "keywords": ("comms", "communication", "коммуникац", "callout", "колл", "инфо"),
    },
    "discipline": {
        "categories": {"decision", "movement", "positioning"},
        "keywords": ("repeat peek", "повторный пик", "discipline", "дисцип", "panic", "паник", "rule", "habit", "привыч"),
    },
    "consistency": {
        "categories": set(),
        "keywords": ("consistency", "стабиль", "variance", "разброс", "repeat", "повтор"),
    },
    "tilt_susceptibility": {
        "categories": set(),
        "keywords": ("tilt", "тильт", "rage", "эмоц", "revenge", "месть"),
    },
}


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except Exception:
        return 0.0


def _signal_matches(focus: str, category: str, text: str) -> bool:
    if focus == "calibration":
        return True
    rule = _FOCUS_RULES.get(focus)
    if not rule:
        return False
    cat = _clean(category, 32).casefold()
    low = _clean(text, 1000).casefold()
    if cat and cat in rule["categories"]:
        return True
    return any(word in low for word in rule["keywords"])


def _active_mission(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed = {
        str(row.get("mission_id") or "").strip()
        for row in events
        if str(row.get("type") or "") == "operator_mission"
        and str(row.get("status") or "").casefold() == "completed"
    }
    accepted = [
        row
        for row in events
        if str(row.get("type") or "") == "operator_mission"
        and str(row.get("status") or "").casefold() == "accepted"
        and str(row.get("mission_id") or "").strip()
        and str(row.get("mission_id") or "").strip() not in completed
        and isinstance(row.get("mission"), Mapping)
    ]
    if not accepted:
        return None
    accepted.sort(key=lambda row: str(row.get("at") or row.get("created_at") or ""), reverse=True)
    mission = dict(accepted[0].get("mission") or {})
    mission["status"] = "active"
    return mission


@dataclass
class MissionEvidenceFusionService:
    store: Any
    enabled: bool | None = None
    min_confidence: float = 0.65

    @property
    def active(self) -> bool:
        if self.enabled is not None:
            return bool(self.enabled)
        return _env_on("MISSION_VOD_EVIDENCE_FUSION_ENABLED")

    def _progression(self, chat_id: int) -> list[dict[str, Any]]:
        fn = getattr(self.store, "list_progression_events", None)
        if not callable(fn):
            return []
        try:
            return [dict(row) for row in list(fn(int(chat_id)) or [])[:100] if isinstance(row, Mapping)]
        except Exception:
            return []

    def _signals(self, result: Any, focus: str) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        for item in list(getattr(result, "mistakes", []) or [])[:12]:
            confidence = _confidence(getattr(item, "confidence", 0.0))
            if confidence < self.min_confidence:
                continue
            label = _clean(getattr(item, "label", ""), 240)
            category = _clean(getattr(item, "category", "unknown"), 32)
            if not label or not _signal_matches(focus, category, label):
                continue
            signals.append({
                "kind": "mistake",
                "label": label,
                "category": category or "unknown",
                "confidence": round(confidence, 3),
                "timestamp": "",
            })

        for item in list(getattr(result, "timeline", []) or [])[:16]:
            confidence = _confidence(getattr(item, "confidence", 0.0))
            if confidence < self.min_confidence:
                continue
            issue = _clean(getattr(item, "issue", ""), 240)
            decision = _clean(getattr(item, "decision", ""), 180)
            correction = _clean(getattr(item, "correction", ""), 180)
            category = _clean(getattr(item, "category", "unknown"), 32)
            combined = " ".join(x for x in (issue, decision, correction) if x)
            if not combined or not _signal_matches(focus, category, combined):
                continue
            signals.append({
                "kind": "timeline",
                "label": issue or decision or correction,
                "category": category or "unknown",
                "confidence": round(confidence, 3),
                "timestamp": _clean(getattr(item, "timestamp", ""), 32),
            })

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in sorted(signals, key=lambda x: float(x.get("confidence") or 0), reverse=True):
            key = (str(item.get("category") or ""), str(item.get("label") or "").casefold())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 8:
                break
        return deduped

    def correlate_vod(self, chat_id: int, result: Any) -> dict[str, Any] | None:
        if not self.active:
            return None
        mission = _active_mission(self._progression(chat_id))
        if not mission:
            return None
        mission_id = _clean(mission.get("id"), 64)
        focus = _clean(mission.get("focus"), 40).casefold() or "calibration"
        if not mission_id:
            return None

        signals = self._signals(result, focus)
        categories = {str(item.get("category") or "") for item in signals if item.get("category")}
        if len(signals) >= 3 and len(categories) >= 2:
            classification = "mission_relevant_evidence_high"
            confidence = "high"
        elif signals:
            classification = "mission_relevant_evidence"
            confidence = "medium" if len(signals) >= 2 else "low"
        else:
            classification = "insufficient_relevant_evidence"
            confidence = "unknown"

        limitations = _clean(getattr(result, "limitations", ""), 500)
        event = {
            "type": EVENT_TYPE,
            "status": "observed",
            "mission_id": mission_id,
            "focus": focus,
            "mission_title": _clean(mission.get("title"), 140),
            "classification": classification,
            "confidence": confidence,
            "evidence_count": len(signals),
            "signals": signals,
            "sampled_frames": len(list(getattr(result, "sampled_timestamps", []) or [])),
            "source": SOURCE,
            "limitations": limitations,
            "does_not_complete_mission": True,
            "at": _now_iso(),
        }

        add_progression = getattr(self.store, "add_progression_event", None)
        if callable(add_progression):
            try:
                add_progression(int(chat_id), event)
            except Exception:
                return None
        else:
            return None

        add_episode = getattr(self.store, "add_episode", None)
        if callable(add_episode):
            try:
                add_episode(int(chat_id), {
                    "kind": EVENT_TYPE,
                    **{key: value for key, value in event.items() if key != "type"},
                })
            except Exception:
                pass
        return event


def format_mission_evidence(event: Mapping[str, Any] | None) -> str:
    if not isinstance(event, Mapping):
        return ""
    title = _clean(event.get("mission_title"), 140) or "CURRENT MISSION"
    classification = _clean(event.get("classification"), 64)
    count = int(event.get("evidence_count") or 0)
    if classification == "insufficient_relevant_evidence":
        verdict = "Клип не дал достаточно релевантных визуальных сигналов по текущей миссии."
    else:
        verdict = f"Найдено релевантных визуальных сигналов: {count}."
    return (
        "\n\nMISSION EVIDENCE // " + title + "\n"
        + verdict
        + "\nЭто sampled-frame evidence, а не автоматический итог миссии. CLEAN/MIXED/FAILED подтверждает игрок после сессии."
    )
