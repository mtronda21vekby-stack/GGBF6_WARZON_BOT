# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from app.services.operator_intelligence.v25 import OperatorIntelligenceService as _V25OperatorIntelligenceService
from app.services.vod.mission_evidence import EVENT_TYPE


_CONFIDENCE_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
_CLASSIFICATION_ORDER = {
    "insufficient_relevant_evidence": 0,
    "mission_relevant_evidence": 1,
    "mission_relevant_evidence_high": 2,
}


class OperatorIntelligenceService(_V25OperatorIntelligenceService):
    """v27 Operator Twin with active-mission evidence fusion telemetry."""

    def _mission_evidence(self, chat_id: int, mission_id: str) -> dict[str, Any] | None:
        events = self._rows("list_progression_events", int(chat_id), 100)
        matched = [
            row for row in events
            if str(row.get("type") or "") == EVENT_TYPE
            and str(row.get("mission_id") or "") == str(mission_id or "")
            and str(row.get("status") or "").casefold() == "observed"
        ]
        if not matched:
            return None
        matched.sort(key=lambda row: str(row.get("at") or row.get("created_at") or ""), reverse=True)
        best_classification = max(
            (str(row.get("classification") or "insufficient_relevant_evidence") for row in matched),
            key=lambda value: _CLASSIFICATION_ORDER.get(value, 0),
        )
        best_confidence = max(
            (str(row.get("confidence") or "unknown") for row in matched),
            key=lambda value: _CONFIDENCE_ORDER.get(value, 0),
        )
        signals: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in matched:
            for raw in list(row.get("signals") or [])[:8]:
                if not isinstance(raw, Mapping):
                    continue
                label = str(raw.get("label") or "").strip()[:240]
                category = str(raw.get("category") or "unknown").strip()[:32]
                key = (category.casefold(), label.casefold())
                if not label or key in seen:
                    continue
                seen.add(key)
                signals.append({
                    "kind": str(raw.get("kind") or "signal")[:24],
                    "label": label,
                    "category": category,
                    "confidence": raw.get("confidence"),
                    "timestamp": str(raw.get("timestamp") or "")[:32],
                })
                if len(signals) >= 8:
                    break
            if len(signals) >= 8:
                break
        return {
            "classification": best_classification,
            "confidence": best_confidence,
            "clips": len(matched),
            "evidence_count": min(999, sum(max(0, int(row.get("evidence_count") or 0)) for row in matched)),
            "sampled_frames": min(9999, sum(max(0, int(row.get("sampled_frames") or 0)) for row in matched)),
            "source": "vision_sampled_frames",
            "latest_at": str(matched[0].get("at") or "")[:64],
            "does_not_complete_mission": True,
            "signals": signals,
        }

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        snapshot = super().snapshot(chat_id)
        mission = snapshot.get("mission") if isinstance(snapshot.get("mission"), dict) else {}
        if str(mission.get("status") or "") != "active":
            return snapshot
        mission_id = str(mission.get("id") or "").strip()
        if not mission_id:
            return snapshot
        evidence = self._mission_evidence(int(chat_id), mission_id)
        if not evidence:
            return snapshot
        session = snapshot.get("session") if isinstance(snapshot.get("session"), dict) else {}
        session["mission_evidence"] = evidence
        snapshot["session"] = session
        mission["evidence_status"] = evidence.get("classification")
        mission["evidence_clips"] = evidence.get("clips")
        snapshot["mission"] = mission
        return snapshot
