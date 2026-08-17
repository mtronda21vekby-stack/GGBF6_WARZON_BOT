from __future__ import annotations

from types import SimpleNamespace

from app.services.operator_intelligence import OperatorIntelligenceService
from app.services.operator_intelligence.context import OperatorContextProjector
from app.services.vod.mission_evidence import MissionEvidenceFusionService, format_mission_evidence


MISSION = {
    "id": "m25-rotation-1",
    "status": "candidate",
    "focus": "rotations",
    "title": "LATE ROTATION DISCIPLINE",
    "objective": "Rotate before zone pressure.",
    "success_condition": "2/3 clean endgames.",
    "confidence": "high",
    "calibration": False,
}


class FakeProfiles:
    def get(self, chat_id):
        return {"game": "Warzone", "difficulty": "Pro", "_chat_id": int(chat_id)}

    def patch(self, chat_id, patch):
        return None


class FakeStore:
    def __init__(self, active=True):
        self.progression = []
        self.episodes = []
        self.training = []
        self.mistakes = []
        self.derived = {}
        if active:
            self.progression.append({
                "type": "operator_mission",
                "status": "accepted",
                "mission_id": MISSION["id"],
                "focus": MISSION["focus"],
                "mission": dict(MISSION),
                "at": "2026-08-17T12:00:00+00:00",
            })

    def list_progression_events(self, chat_id):
        return list(self.progression)

    def add_progression_event(self, chat_id, event):
        self.progression.insert(0, dict(event))

    def add_episode(self, chat_id, event):
        self.episodes.insert(0, dict(event))

    def list_episodes(self, chat_id, limit=20):
        return list(self.episodes)[:limit]

    def list_training_sessions(self, chat_id):
        return list(self.training)

    def list_mistake_stats(self, chat_id):
        return list(self.mistakes)

    def get_derived_intelligence(self, chat_id):
        return dict(self.derived)


def vod_result(*, high=True, relevant=True):
    label = "Late rotation after low-value chase into gas" if relevant else "Clean recoil control at range"
    category = "positioning" if relevant else "aim"
    confidence = 0.91 if high else 0.42
    return SimpleNamespace(
        mistakes=[SimpleNamespace(label=label, category=category, confidence=confidence)],
        timeline=[
            SimpleNamespace(
                timestamp="00:17",
                category="decision" if relevant else "aim",
                confidence=0.88 if high else 0.40,
                issue="Delayed rotation while chasing damage" if relevant else "Good centering",
                decision="Stayed too long" if relevant else "Held angle",
                correction="Rotate before gas pressure" if relevant else "Keep crosshair stable",
            )
        ],
        sampled_timestamps=[0.0, 8.0, 17.0, 25.0],
        limitations="Sampled frames only; no continuous-video tracking.",
    )


def test_high_confidence_vod_correlates_to_active_mission_without_autocomplete():
    store = FakeStore(active=True)
    event = MissionEvidenceFusionService(store=store).correlate_vod(7, vod_result())
    assert event is not None
    assert event["mission_id"] == MISSION["id"]
    assert event["focus"] == "rotations"
    assert event["source"] == "vision_sampled_frames"
    assert event["does_not_complete_mission"] is True
    assert event["evidence_count"] >= 2
    assert event["classification"] in {"mission_relevant_evidence", "mission_relevant_evidence_high"}
    assert any(row.get("type") == "operator_mission_evidence" for row in store.progression)
    assert not any(
        row.get("type") == "operator_mission" and row.get("status") == "completed"
        for row in store.progression
    )
    rendered = format_mission_evidence(event)
    assert "sampled-frame evidence" in rendered
    assert "CLEAN/MIXED/FAILED" in rendered
    assert "не автоматический итог" in rendered


def test_low_confidence_or_irrelevant_vod_is_not_promoted_to_mission_signal():
    store = FakeStore(active=True)
    event = MissionEvidenceFusionService(store=store).correlate_vod(7, vod_result(high=False, relevant=True))
    assert event is not None
    assert event["classification"] == "insufficient_relevant_evidence"
    assert event["confidence"] == "unknown"
    assert event["evidence_count"] == 0

    other = FakeStore(active=True)
    event2 = MissionEvidenceFusionService(store=other).correlate_vod(7, vod_result(high=True, relevant=False))
    assert event2 is not None
    assert event2["classification"] == "insufficient_relevant_evidence"
    assert event2["evidence_count"] == 0


def test_no_active_mission_or_rollback_produces_no_fusion_event(monkeypatch):
    assert MissionEvidenceFusionService(store=FakeStore(active=False)).correlate_vod(7, vod_result()) is None
    monkeypatch.setenv("MISSION_VOD_EVIDENCE_FUSION_ENABLED", "0")
    assert MissionEvidenceFusionService(store=FakeStore(active=True)).correlate_vod(7, vod_result()) is None


def test_operator_snapshot_and_context_expose_evidence_but_not_outcome_authority():
    store = FakeStore(active=True)
    fusion = MissionEvidenceFusionService(store=store).correlate_vod(7, vod_result())
    assert fusion is not None

    snapshot = OperatorIntelligenceService(
        store=store,
        profiles=FakeProfiles(),
        operator_enabled=True,
        missions_enabled=True,
    ).snapshot(7)
    assert snapshot["mission"]["status"] == "active"
    evidence = snapshot["session"]["mission_evidence"]
    assert evidence["does_not_complete_mission"] is True
    assert evidence["source"] == "vision_sampled_frames"
    assert snapshot["session"]["phase"] == "LIVE_OBJECTIVE"

    projected = OperatorContextProjector().project(snapshot)
    assert projected["schema"] == "bco_operator_context_v27"
    projected_evidence = projected["session"]["mission_evidence"]
    assert projected_evidence["does_not_complete_mission"] is True
    assert projected_evidence["source"] == "vision_sampled_frames"
    assert "weight" not in repr(projected_evidence)
    assert "outcome" not in projected_evidence
