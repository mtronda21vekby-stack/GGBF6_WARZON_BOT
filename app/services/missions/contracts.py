from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MISSION_STATUSES = frozenset({"candidate", "active", "completed", "failed", "superseded"})
MISSION_FOCUS_DOMAINS = frozenset({"aim", "movement", "positioning", "decision", "comms"})


@dataclass(frozen=True, slots=True)
class MissionCompletionReport:
    """Bounded, provider-independent operator report for one mission."""

    success: bool
    note: str = ""
    score: float | None = None
    matches: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> dict[str, Any]:
        score = self.score
        if score is not None:
            score = max(-1_000_000.0, min(1_000_000.0, float(score)))
        matches = self.matches
        if matches is not None:
            matches = max(0, min(10_000, int(matches)))
        evidence = {
            str(key)[:64]: value
            for key, value in list((self.evidence or {}).items())[:20]
            if str(key).strip()
        }
        return {
            "success": bool(self.success),
            "note": str(self.note or "").strip()[:1200],
            "score": score,
            "matches": matches,
            "evidence": evidence,
        }


def validate_mission_payload(mission: dict[str, Any]) -> dict[str, Any]:
    """Validate the public mission shape without persisting or trusting it."""
    if not isinstance(mission, dict):
        raise TypeError("mission must be a dict")
    mission_id = str(mission.get("id") or "").strip()
    status = str(mission.get("status") or "candidate").strip().casefold()
    focus = str(mission.get("focus") or "").strip().casefold()
    title = str(mission.get("title") or "").strip()
    objective = str(mission.get("objective") or "").strip()
    metric = str(mission.get("success_metric") or "").strip()
    protocol = mission.get("protocol") or []

    if not mission_id or len(mission_id) > 160:
        raise ValueError("invalid mission id")
    if status not in MISSION_STATUSES:
        raise ValueError("invalid mission status")
    if focus not in MISSION_FOCUS_DOMAINS:
        raise ValueError("invalid mission focus")
    if not title or not objective or not metric:
        raise ValueError("mission is not measurable")
    if not isinstance(protocol, list) or not protocol:
        raise ValueError("mission protocol is empty")

    return {
        **mission,
        "id": mission_id,
        "status": status,
        "focus": focus,
        "title": title[:120],
        "objective": objective[:1200],
        "success_metric": metric[:1200],
        "protocol": [str(step).strip()[:800] for step in protocol[:12] if str(step).strip()],
    }
