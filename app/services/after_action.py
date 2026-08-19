# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from app.services.crown_session import CrownSessionService
from app.services.operator_intelligence.orchestrated_service import OrchestratedOperatorIntelligenceService
from app.services.operator_intelligence.strategy_outcomes import PremiumStrategyOutcomeService


class CrownAfterActionService:
    """Close one explicit mission cycle and return a measurable post-session report.

    VOD remains evidence-only: it can inform the report but never auto-completes a
    mission. Strategy evaluation remains associative and never claims causation.
    """

    def __init__(self, *, store: Any, profiles: Any, entitlements: Any = None) -> None:
        self.store = store
        self.profiles = profiles
        self.entitlements = entitlements

    @staticmethod
    def _mistake_labels(session: Mapping[str, Any]) -> list[str]:
        rows = ((session.get("personal_meta") or {}).get("top_mistakes") or [])
        out: list[str] = []
        for row in rows:
            if isinstance(row, Mapping):
                label = str(row.get("label") or "").strip()
                if label and label not in out:
                    out.append(label[:180])
        return out[:8]

    @staticmethod
    def _score_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
        b = ((before.get("personal_meta") or {}).get("scores") or {})
        a = ((after.get("personal_meta") or {}).get("scores") or {})
        out: list[dict[str, Any]] = []
        for key in sorted(set(b) | set(a)):
            bv, av = b.get(key), a.get(key)
            if bv is None or av is None or bv == av:
                continue
            try:
                delta = round(float(av) - float(bv), 3)
            except Exception:
                continue
            out.append({"metric": str(key)[:40], "before": bv, "after": av, "delta": delta})
        return out[:12]

    @staticmethod
    def _latest_vod(session: Mapping[str, Any]) -> dict[str, Any] | None:
        rows = ((session.get("player") or {}).get("vod_reviews") or [])
        if not rows or not isinstance(rows[0], Mapping):
            return None
        row = dict(rows[0])
        return {
            "game": str(row.get("game") or "")[:40],
            "at": str(row.get("at") or "")[:64] or None,
            "summary": str(row.get("summary") or "")[:500],
            "confirmed_mistakes": [str(x)[:160] for x in list(row.get("confirmed_mistakes") or [])[:6]],
            "authority": "sampled_frame_evidence_only",
            "auto_completed_mission": False,
        }

    async def complete(
        self,
        *,
        chat_id: int,
        telegram_user_id: int,
        mission_id: str,
        outcome: str,
        metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        cid = int(chat_id)
        uid = int(telegram_user_id)
        session_service = CrownSessionService(store=self.store, profiles=self.profiles, entitlements=self.entitlements)
        before = await session_service.snapshot(chat_id=cid, telegram_user_id=uid)

        operator = OrchestratedOperatorIntelligenceService.from_components(store=self.store, profiles=self.profiles)
        completed = operator.complete(cid, str(mission_id or ""), outcome=str(outcome or "reported"), metrics=dict(metrics or {}))
        after = await session_service.snapshot(chat_id=cid, telegram_user_id=uid)

        before_mistakes = self._mistake_labels(before)
        after_mistakes = self._mistake_labels(after)
        new_weaknesses = [x for x in after_mistakes if x not in before_mistakes]
        strategy = PremiumStrategyOutcomeService(self.store).snapshot(cid)
        next_mission = after.get("next_mission") or after.get("mission") or completed.get("next_mission")

        return {
            "schema": "crown-after-action-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mission_outcome": {
                "mission_id": str(mission_id or "")[:64],
                "outcome": str(outcome or "reported")[:32],
                "explicit_operator_report": True,
                "vod_auto_complete": False,
            },
            "what_changed": {
                "coverage_before": int((before.get("personal_meta") or {}).get("coverage") or 0),
                "coverage_after": int((after.get("personal_meta") or {}).get("coverage") or 0),
                "score_changes": self._score_changes(before, after),
                "operator_state_before": str((before.get("operator_twin") or {}).get("readiness") or "unknown")[:40],
                "operator_state_after": str((after.get("operator_twin") or {}).get("readiness") or "unknown")[:40],
            },
            "new_weaknesses": new_weaknesses[:4],
            "latest_vod_evidence": self._latest_vod(after),
            "strategy_outcome": {
                "latest": strategy.get("latest"),
                "association_not_causation": True,
            },
            "next_mission": next_mission,
            "session": after,
            "truth_contract": {
                "explicit_outcome_authoritative": True,
                "vod_evidence_only": True,
                "new_weakness_requires_new_persisted_evidence": True,
                "strategy_effectiveness_is_associative": True,
                "causal_claims": False,
            },
        }
