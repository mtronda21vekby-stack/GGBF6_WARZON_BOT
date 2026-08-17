# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Mapping

from app.services.operator_intelligence.mission_orchestrator import MissionOrchestrator
from app.services.operator_intelligence.v28 import OperatorIntelligenceService as CurrentOperatorIntelligenceService


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


class OrchestratedOperatorIntelligenceService:
    """Add v36 mission staging without changing established mission authority.

    The wrapped current Operator service (v28 including v27 evidence fusion)
    remains authoritative for mission IDs, accept, complete, persistence,
    longitudinal intelligence and stale-action rejection. v36 only derives and
    projects a training stage from persisted explicit mission history.
    """

    def __init__(
        self,
        *,
        store: Any = None,
        profiles: Any = None,
        operator_enabled: bool = True,
        missions_enabled: bool = True,
        orchestrator_enabled: bool | None = None,
        base: CurrentOperatorIntelligenceService | None = None,
    ) -> None:
        self.base = base or CurrentOperatorIntelligenceService(
            store=store,
            profiles=profiles,
            operator_enabled=operator_enabled,
            missions_enabled=missions_enabled,
        )
        self.orchestrator_enabled = (
            _env_on("MISSION_ORCHESTRATOR_ENABLED")
            if orchestrator_enabled is None
            else bool(orchestrator_enabled)
        )

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
            store=store,
            profiles=profiles,
            operator_enabled=operator_enabled,
            missions_enabled=missions_enabled,
            orchestrator_enabled=orchestrator_enabled,
        )

    @property
    def store(self) -> Any:
        return self.base.store

    @property
    def profiles(self) -> Any:
        return self.base.profiles

    @property
    def operator_enabled(self) -> bool:
        return bool(self.base.operator_enabled)

    @property
    def missions_enabled(self) -> bool:
        return bool(self.base.missions_enabled)

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
        return self._apply(int(chat_id), self.base.accept(int(chat_id), mission_id))

    def complete(
        self,
        chat_id: int,
        mission_id: str,
        *,
        outcome: str = "reported",
        metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.base.complete(
            int(chat_id),
            mission_id,
            outcome=outcome,
            metrics=metrics,
        )
        return self._apply(int(chat_id), result)
