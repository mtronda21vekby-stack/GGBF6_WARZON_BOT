# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from app.services.crown_session import CrownSessionService
from app.services.operator_intelligence.orchestrated_service import OrchestratedOperatorIntelligenceService
from app.services.operator_intelligence.strategy_outcomes import PremiumStrategyOutcomeService
from app.services.session_cycle import CrownSessionCycleService


class CrownAfterActionService:
    """Close one explicit mission cycle and return a session-scoped measurable report."""

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
            try: delta = round(float(av) - float(bv), 3)
            except Exception: continue
            out.append({"metric": str(key)[:40], "before": bv, "after": av, "delta": delta})
        return out[:12]

    def _progression(self, chat_id: int) -> list[dict[str, Any]]:
        fn = getattr(self.store, "list_progression_events", None)
        if not callable(fn): return []
        try: rows = fn(int(chat_id), 220)
        except TypeError: rows = fn(int(chat_id))
        except Exception: return []
        return [dict(x) for x in list(rows or []) if isinstance(x, Mapping)]

    def _session_vod_evidence(self, rows: list[dict[str, Any]], crown_session_id: str, mission_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("type") or "") != "operator_mission_evidence": continue
            if str(row.get("mission_id") or "") != str(mission_id or ""): continue
            if crown_session_id and str(row.get("crown_session_id") or "") != crown_session_id: continue
            out.append({
                "crown_session_id": str(row.get("crown_session_id") or "")[:64] or None,
                "mission_id": str(row.get("mission_id") or "")[:64],
                "classification": str(row.get("classification") or "")[:64],
                "confidence": str(row.get("confidence") or "unknown")[:24],
                "evidence_count": int(row.get("evidence_count") or 0),
                "signals": list(row.get("signals") or [])[:8],
                "sampled_frames": int(row.get("sampled_frames") or 0),
                "limitations": str(row.get("limitations") or "")[:500],
                "at": str(row.get("at") or row.get("created_at") or "")[:64] or None,
                "authority": "sampled_frame_evidence_only",
                "auto_completed_mission": False,
            })
        out.sort(key=lambda x: str(x.get("at") or ""), reverse=True)
        return out[:4]

    def _session_engagements(self, rows: list[dict[str, Any]], crown_session_id: str, mission_id: str) -> list[dict[str, Any]]:
        matches = []
        for row in rows:
            if str(row.get("type") or "") != "vod_engagement_intelligence": continue
            if str(row.get("mission_id") or "") != str(mission_id or ""): continue
            if crown_session_id and str(row.get("crown_session_id") or "") != crown_session_id: continue
            matches.extend(list(row.get("engagements") or [])[:12])
        out = []
        for item in matches[:12]:
            if not isinstance(item, Mapping): continue
            out.append({
                "engagement_id": str(item.get("engagement_id") or "")[:32],
                "timestamp": str(item.get("timestamp") or "")[:32] or None,
                "entry": str(item.get("entry") or "")[:420] or None,
                "first_damage": item.get("first_damage"),
                "position": str(item.get("position") or "")[:420] or None,
                "decision": str(item.get("decision") or "")[:320] or None,
                "result": str(item.get("result") or "")[:320] or None,
                "correction": str(item.get("correction") or "")[:360] or None,
                "category": str(item.get("category") or "unknown")[:32],
                "confidence": item.get("confidence"),
                "sampled_frame_only": True,
            })
        return out

    async def complete(self, *, chat_id: int, telegram_user_id: int, mission_id: str, outcome: str, metrics: Mapping[str, Any] | None = None) -> dict[str, Any]:
        cid = int(chat_id); uid = int(telegram_user_id)
        mission_id = str(mission_id or "")[:64]; outcome = str(outcome or "reported")[:32]
        session_service = CrownSessionService(store=self.store, profiles=self.profiles, entitlements=self.entitlements)
        before = await session_service.snapshot(chat_id=cid, telegram_user_id=uid)
        cycle_service = CrownSessionCycleService(self.store)
        cycle = cycle_service.current(cid, mission_id)
        crown_session_id = str((cycle or {}).get("crown_session_id") or "")[:64]
        rows = self._progression(cid)
        linked_vod = self._session_vod_evidence(rows, crown_session_id, mission_id)
        engagements = self._session_engagements(rows, crown_session_id, mission_id)

        operator = OrchestratedOperatorIntelligenceService.from_components(store=self.store, profiles=self.profiles)
        completed = operator.complete(cid, mission_id, outcome=outcome, metrics=dict(metrics or {}))
        cycle_close = cycle_service.close(cid, crown_session_id, mission_id, outcome) if crown_session_id else None
        after = await session_service.snapshot(chat_id=cid, telegram_user_id=uid)

        before_mistakes = self._mistake_labels(before); after_mistakes = self._mistake_labels(after)
        new_weaknesses = [x for x in after_mistakes if x not in before_mistakes]
        strategy = PremiumStrategyOutcomeService(self.store).snapshot(cid)
        next_mission = after.get("next_mission") or after.get("mission") or completed.get("next_mission")

        return {
            "schema": "crown-after-action-v3",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "crown_session": {"id": crown_session_id or None, "status": "closed" if cycle_close else "untracked", "mission_id": mission_id, "evidence_items": len(linked_vod), "engagements": len(engagements), "authority": "server_progression_event" if crown_session_id else "legacy_untracked"},
            "mission_outcome": {"mission_id": mission_id, "outcome": outcome, "explicit_operator_report": True, "vod_auto_complete": False},
            "what_changed": {
                "coverage_before": int((before.get("personal_meta") or {}).get("coverage") or 0),
                "coverage_after": int((after.get("personal_meta") or {}).get("coverage") or 0),
                "score_changes": self._score_changes(before, after),
                "operator_state_before": str((before.get("operator_twin") or {}).get("readiness") or "unknown")[:40],
                "operator_state_after": str((after.get("operator_twin") or {}).get("readiness") or "unknown")[:40],
            },
            "new_weaknesses": new_weaknesses[:4],
            "linked_vod_evidence": linked_vod,
            "engagements": engagements,
            "strategy_outcome": {"latest": strategy.get("latest"), "association_not_causation": True},
            "next_mission": next_mission,
            "session": after,
            "truth_contract": {
                "explicit_outcome_authoritative": True,
                "vod_evidence_only": True,
                "vod_must_match_session_and_mission": bool(crown_session_id),
                "engagements_are_sampled_frame_observations": True,
                "continuous_video_claimed": False,
                "new_weakness_requires_new_persisted_evidence": True,
                "strategy_effectiveness_is_associative": True,
                "causal_claims": False,
            },
        }
