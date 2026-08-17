from __future__ import annotations

from app.services.operator_intelligence.context import OperatorContextProjector
from app.services.operator_intelligence.v28 import OperatorIntelligenceService
from app.services.storage.memory import InMemoryStore


class Profiles:
    def get(self, chat_id: int):
        return {}

    def patch(self, chat_id: int, patch):
        return None


def _completed(store: InMemoryStore, mission_id: str, outcome: str, at: str, *, focus: str = "rotations") -> None:
    store.add_progression_event(1, {
        "type": "operator_mission",
        "status": "completed",
        "mission_id": mission_id,
        "focus": focus,
        "outcome": outcome,
        "metrics": {"mission_score": {"clean": 100, "mixed": 60, "failed": 20}[outcome]},
        "source": "explicit_operator_report",
        "at": at,
    })


def test_one_or_two_cycles_never_become_directional_trend(monkeypatch):
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "1")
    store = InMemoryStore()
    _completed(store, "m1", "failed", "2026-08-01T00:00:00+00:00")
    _completed(store, "m2", "clean", "2026-08-02T00:00:00+00:00")

    snapshot = OperatorIntelligenceService(store=store, profiles=Profiles()).snapshot(1)
    longi = snapshot["longitudinal"]

    assert longi["completed_cycles"] == 2
    assert longi["directional_ready"] is False
    assert longi["trend"] == "unknown"
    assert longi["single_session_proves_improvement"] is False
    assert longi["causal_claims"] is False


def test_three_cycles_enable_direction_without_claiming_causation(monkeypatch):
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "1")
    store = InMemoryStore()
    _completed(store, "m1", "failed", "2026-08-01T00:00:00+00:00")
    _completed(store, "m2", "mixed", "2026-08-02T00:00:00+00:00")
    _completed(store, "m3", "clean", "2026-08-03T00:00:00+00:00")

    snapshot = OperatorIntelligenceService(store=store, profiles=Profiles()).snapshot(1)
    longi = snapshot["longitudinal"]

    assert longi["directional_ready"] is True
    assert longi["trend"] == "improving"
    assert longi["association_rule"] == "association_not_causation"
    assert longi["causal_claims"] is False


def test_clean_outcome_plus_high_vod_evidence_is_preserved_as_contradiction(monkeypatch):
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "1")
    store = InMemoryStore()
    _completed(store, "m1", "failed", "2026-08-01T00:00:00+00:00")
    _completed(store, "m2", "mixed", "2026-08-02T00:00:00+00:00")
    _completed(store, "m3", "clean", "2026-08-03T00:00:00+00:00")
    store.add_progression_event(1, {
        "type": "operator_mission_evidence",
        "status": "observed",
        "mission_id": "m3",
        "focus": "rotations",
        "classification": "mission_relevant_evidence_high",
        "source": "vision_sampled_frames",
        "does_not_complete_mission": True,
        "at": "2026-08-03T00:05:00+00:00",
    })

    snapshot = OperatorIntelligenceService(store=store, profiles=Profiles()).snapshot(1)
    longi = snapshot["longitudinal"]

    assert longi["contradiction_detected"] is True
    assert longi["contradictions"] == 1
    assert longi["confidence"] == "medium"
    assert snapshot["operator"]["contradiction_detected"] is True


def test_prompt_safe_context_contains_longitudinal_contract_without_internal_scores(monkeypatch):
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "1")
    projected = OperatorContextProjector().project({
        "operator": {"dimensions": {}, "truth_model": {}},
        "mission": {},
        "session": {},
        "longitudinal": {
            "completed_cycles": 4,
            "directional_ready": True,
            "trend": "stable",
            "volatility": "moderate",
            "confidence": "medium",
            "contradictions": 1,
            "contradiction_detected": True,
            "vod_correlated_cycles": 2,
            "dominant_focus": "rotations",
            "interpretation": "bounded",
            "secret_weight": 999,
        },
    })

    assert projected["schema"] == "bco_operator_context_v28"
    assert projected["longitudinal"]["association_rule"] == "association_not_causation"
    assert projected["longitudinal"]["causal_claims"] is False
    assert "secret_weight" not in projected["longitudinal"]


def test_longitudinal_layer_has_isolated_rollback(monkeypatch):
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "0")
    store = InMemoryStore()
    _completed(store, "m1", "failed", "2026-08-01T00:00:00+00:00")
    _completed(store, "m2", "mixed", "2026-08-02T00:00:00+00:00")
    _completed(store, "m3", "clean", "2026-08-03T00:00:00+00:00")

    snapshot = OperatorIntelligenceService(store=store, profiles=Profiles()).snapshot(1)
    assert "longitudinal" not in snapshot
