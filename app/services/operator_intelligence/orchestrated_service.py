# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from app.services.operator_intelligence.mission_orchestrator import MissionOrchestrator
from app.services.operator_intelligence.service import OperatorIntelligenceService


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


@dataclass
class OrchestratedOperatorIntelligenceService:
    """Add v36 mission staging without changing v25 mission authority.

    The wrapped v25 service remains the authority for mission IDs, accept,
    complete, persistence, stale-action rejection, and explicit outcomes. This
    wrapper only derives and projects the v36 training stage from persisted
    explicit mission history.
    """

    base: OperatorIntelligenceService
    orchestrator_enabled: bool = True

    @classmethod
    def from_components(
        cls,
        *,
        store: Any,
        profiles: Any,
        operator_enabled: bool = True,
        missions_enabled: bool = True,
        orchestrator_enabled: bool | None = None,
    ) -> "OrchestratedOperatorIntelligenceService":
        return cls(
            base=OperatorIntelligenceService(
                store=store,
                profiles=profiles,
                operator_enabled=operator_enabled,
                missions_enabled=missions_enabled,
            ),
            orchestrator_enabled=(
                _env_on("MISSION_ORCHESTRATOR_ENABLED")
                if orchestrator_enabled is None
                else bool(orchestrator_enabled)
            ),
        )

    @property
    def store(self) -> Any:
        return self.base.store

    @property
    def profiles(self) -> Any:
        return self.base.profiles

    def _progression(self, chat_id: int) -> list[dict[str, Any]]:
        fn = getattr(self.store, "list_progression_events", None)
        if not callable(fn):
            return []
        try:
            rows = fn(int(chat_id), 120)
        except TypeError:
            try:
                rows = fn(int(chat_id))
            except Exception:
                return []
        except Exception:
            return []
        return [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]

    def _decorate_mission(
        self,
        mission: Mapping[str, Any] | None,
        progression: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not isinstance(mission, Mapping):
            return None
        raw = dict(mission)
        focus = str(raw.get("focus") or "calibration").strip().casefold()[:40]
        orchestration = MissionOrchestrator.snapshot(progression, focus)
        if str(raw.get("status") or "").casefold() == "active":
            return MissionOrchestrator.annotate_active(raw, orchestration)
        return MissionOrchestrator.decorate_candidate(raw, orchestration)

    def _apply(self, chat_id: int, snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
        data = dict(snapshot or {})
        if not self.orchestrator_enabled:
            data["mission_orchestrator"] = {
                "enabled": False,
                "schema": "disabled_v35_behavior",
                "transition_authority": "explicit_operator_report_only",
                "vod_transition_authority": False,
            }
            return data

        progression = self._progression(int(chat_id))
        mission = self._decorate_mission(data.get("mission"), progression)
        if mission is not None:
            data["mission"] = mission
            orchestration = dict(mission.get("orchestrator") or {})
        else:
            orchestration = MissionOrchestrator.snapshot(progression, "calibration")

        session = dict(data.get("session") or {})
        session["orchestrator_stage"] = str(orchestration.get("stage") or "CALIBRATION")
        session["orchestrator"] = orchestration
        data["session"] = session
        data["mission_orchestrator"] = {
            "enabled": True,
            **orchestration,
        }

        next_mission = self._decorate_mission(data.get("next_mission"), progression)
        if next_mission is not None:
            data["next_mission"] = next_mission

        return data

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        return self._apply(int(chat_id), self.base.snapshot(int(chat_id)))

    def accept(self, chat_id: int, mission_id: str) -> dict[str, Any]:
        # Base service validates the exact v25 mission ID and records acceptance.
        return self._apply(int(chat_id), self.base.accept(int(chat_id), mission_id))

    def complete(
        self,
        chat_id: int,
        mission_id: str,
        *,
        outcome: str = "reported",
        metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Base service remains the only completion writer. The orchestrator sees
        # the new explicit outcome only after that write has completed.
        result = self.base.complete(
            int(chat_id),
            mission_id,
            outcome=outcome,
            metrics=metrics,
        )
        return self._apply(int(chat_id), result)
