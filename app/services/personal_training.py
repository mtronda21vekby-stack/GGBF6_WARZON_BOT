# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from app.services.training.service import TrainingService
from app.services.operator_intelligence.orchestrated_service import OrchestratedOperatorIntelligenceService


FOCUS_ALIASES = {
    "aim": "aim",
    "movement": "movement",
    "position": "positioning",
    "positioning": "positioning",
    "rotations": "positioning",
    "decision": "positioning",
    "discipline": "positioning",
}


class PersonalTrainingProtocolService:
    """Build an explainable training protocol from trusted player evidence.

    Manual focus is an explicit override. Otherwise we select the strongest
    limiting signal from Operator Twin, then fall back to mission wording and
    finally the saved profile focus. No hidden score is invented here.
    """

    def __init__(self, *, store: Any, profiles: Any) -> None:
        self.store = store
        self.profiles = profiles

    @staticmethod
    def _map_focus(name: str) -> str:
        return FOCUS_ALIASES.get(str(name or "").strip().casefold(), "positioning")

    def _auto_focus(self, operator: Mapping[str, Any], mission: Mapping[str, Any], profile: Mapping[str, Any]) -> tuple[str, str]:
        dims = dict((operator.get("operator") or {}).get("dimensions") or {})
        limiting = []
        for name, data in dims.items():
            if str((data or {}).get("assessment") or "") != "limiting_signal":
                continue
            limiting.append((int((data or {}).get("evidence_count") or 0), name))
        if limiting:
            limiting.sort(reverse=True)
            raw = limiting[0][1]
            return self._map_focus(raw), f"Operator Twin limiting signal: {raw}"

        mission_text = " ".join(str(mission.get(k) or "") for k in ("title", "objective", "basis")).casefold()
        for keyword, focus in (("aim", "aim"), ("movement", "movement"), ("slide", "movement"), ("position", "positioning"), ("rotation", "positioning"), ("decision", "positioning"), ("discipline", "positioning")):
            if keyword in mission_text:
                return focus, f"Active mission context: {keyword}"

        saved = str(profile.get("training_focus") or "aim")
        return self._map_focus(saved), "Saved player training focus"

    def build(self, *, chat_id: int, manual_focus: str = "") -> dict[str, Any]:
        profile = dict(self.profiles.get(chat_id) or {})
        snapshot = OrchestratedOperatorIntelligenceService.from_components(store=self.store, profiles=self.profiles).snapshot(chat_id)
        mission = dict(snapshot.get("mission") or snapshot.get("next_mission") or {})

        if str(manual_focus or "").strip():
            focus = self._map_focus(manual_focus)
            basis = "Manual player override"
            authority = "explicit_override"
        else:
            focus, basis = self._auto_focus(snapshot, mission, profile)
            authority = "operator_evidence"

        plan = TrainingService().build(focus=focus, profile=profile)
        blocks = list(plan.blocks)
        if mission.get("objective"):
            blocks[-1] = f"5 min: match-like application against current mission — {str(mission.get('objective'))[:180]}"

        return {
            "schema": "crown-personal-training-v1",
            "focus": focus,
            "focus_authority": authority,
            "basis": basis,
            "objective": plan.objective,
            "blocks": blocks,
            "metric": plan.metric,
            "stop_condition": plan.stop_condition,
            "mission": {
                "id": mission.get("id"),
                "title": mission.get("title"),
                "status": mission.get("status"),
                "objective": mission.get("objective"),
            },
            "world": profile.get("game") or "FPS",
            "input": profile.get("input") or profile.get("platform") or "UNKNOWN",
            "brain_mode": profile.get("difficulty") or profile.get("mode") or "Normal",
            "truth": {
                "hidden_score": False,
                "causal_claim": False,
                "evidence_source": "Operator Twin + active mission + explicit player profile",
            },
        }
