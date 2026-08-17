# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from app.services.operator_intelligence.service import (
    MISSION_EVENT_TYPE,
    MissionConflict,
    OperatorIntelligenceService as _BaseOperatorIntelligenceService,
)


class OperatorIntelligenceService(_BaseOperatorIntelligenceService):
    """v25 hardening around the core evidence/mission engine.

    Calibration missions participate in the deterministic cycle counter, and
    state-changing actions are only acknowledged when the persisted snapshot
    proves the transition actually happened.
    """

    def _mission_history(self, progression: list[dict[str, Any]]) -> dict[str, Any]:
        state = super()._mission_history(progression)
        completions = dict(state.get("completions") or {})
        completions["calibration"] = sum(
            1
            for row in progression
            if str(row.get("type") or "") == MISSION_EVENT_TYPE
            and str(row.get("status") or "").casefold() == "completed"
            and str(row.get("focus") or "").casefold() == "calibration"
        )
        state["completions"] = completions
        return state

    def accept(self, chat_id: int, mission_id: str) -> dict[str, Any]:
        accepted = super().accept(chat_id, mission_id)
        if str((accepted.get("mission") or {}).get("status") or "") != "active":
            raise MissionConflict("mission_persistence_unavailable")
        return accepted

    def complete(self, chat_id: int, mission_id: str, **kwargs: Any) -> dict[str, Any]:
        completed = super().complete(chat_id, mission_id, **kwargs)
        next_mission = dict(completed.get("next_mission") or completed.get("mission") or {})
        if str(next_mission.get("id") or "") == str(mission_id or ""):
            raise MissionConflict("mission_completion_persistence_unavailable")
        return completed
