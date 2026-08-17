from __future__ import annotations

import pytest

from app.services.operator_intelligence import MissionConflict, OperatorIntelligenceService


class FakeProfiles:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, chat_id):
        return dict(self.data)

    def patch(self, chat_id, patch):
        self.data.update(dict(patch or {}))


class FakeStore:
    def __init__(self):
        self.mistakes = []
        self.progression = []
        self.training = []
        self.episodes = []
        self.derived = {}
        self.summary = ""

    def list_mistake_stats(self, chat_id):
        return list(self.mistakes)

    def list_progression_events(self, chat_id):
        return list(self.progression)

    def list_training_sessions(self, chat_id):
        return list(self.training)

    def list_episodes(self, chat_id, limit=20):
        return list(self.episodes)[:limit]

    def get_derived_intelligence(self, chat_id):
        return dict(self.derived)

    def set_derived_intelligence(self, chat_id, value):
        self.derived = dict(value or {})

    def set_summary(self, chat_id, value):
        self.summary = str(value or "")

    def add_progression_event(self, chat_id, event):
        self.progression.insert(0, dict(event))

    def add_training_session(self, chat_id, event):
        self.training.insert(0, dict(event))

    def add_episode(self, chat_id, event):
        self.episodes.insert(0, dict(event))


def service(store=None, profiles=None):
    return OperatorIntelligenceService(
        store=store or FakeStore(),
        profiles=profiles or FakeProfiles(),
        operator_enabled=True,
        missions_enabled=True,
    )


def test_unknown_remains_unknown_and_generates_calibration_mission():
    snapshot = service().snapshot(7)
    op = snapshot["operator"]
    assert op["unknown_remains_unknown"] is True
    assert op["readiness"] == "INSUFFICIENT_DATA"
    assert op["risk"] == "UNKNOWN"
    assert op["dimensions"]["tilt_susceptibility"]["claim_class"] == "unknown"
    assert "score" not in op["dimensions"]["tilt_susceptibility"]
    assert snapshot["mission"]["calibration"] is True
    assert snapshot["mission"]["focus"] == "calibration"


def test_repeated_rotation_evidence_selects_rotation_mission_without_fake_skill_score():
    store = FakeStore()
    store.mistakes = [{
        "label": "Поздняя ротация: остаюсь в зоне ради килла",
        "count": 4,
        "last_seen": "2026-08-17T10:00:00+00:00",
    }]
    store.episodes = [{
        "kind": "vod_sampled_frames",
        "confirmed_mistakes": ["late rotation and gas timing"],
        "at": "2026-08-17T10:10:00+00:00",
    }]
    snapshot = service(store, FakeProfiles({"game": "Warzone"})).snapshot(7)
    rotations = snapshot["operator"]["dimensions"]["rotations"]
    assert rotations["assessment"] == "limiting_signal"
    assert rotations["claim_class"] in {"weak_pattern", "high_confidence_player_pattern"}
    assert rotations["evidence_count"] >= 2
    assert "score" not in rotations
    assert snapshot["mission"]["focus"] == "rotations"
    assert snapshot["mission"]["title"] == "LATE ROTATION DISCIPLINE"


def test_mission_lifecycle_is_persistent_and_stale_ids_fail_closed():
    store = FakeStore()
    profiles = FakeProfiles({"game": "Warzone"})
    svc = service(store, profiles)
    candidate = svc.snapshot(11)["mission"]

    accepted = svc.accept(11, candidate["id"])
    assert accepted["mission"]["status"] == "active"
    assert accepted["session"]["phase"] == "LIVE_OBJECTIVE"

    with pytest.raises(MissionConflict):
        svc.accept(11, "m25-stale")

    completed = svc.complete(
        11,
        candidate["id"],
        outcome="clean",
        metrics={"matches": 3, "clean_executions": 2, "death_cause": "late gas"},
    )
    assert completed["session"]["phase"] == "POST_SESSION_REVIEW"
    assert completed["session"]["memory_update"] == "complete"
    assert completed["session"]["last_review"]["outcome"] == "clean"
    assert completed["next_mission"]["status"] == "candidate"
    assert completed["next_mission"]["id"] != candidate["id"]
    assert any(x.get("status") == "completed" for x in store.progression)

    with pytest.raises(MissionConflict):
        svc.complete(11, candidate["id"], outcome="clean")


def test_mission_metrics_are_bounded_and_allowlisted():
    store = FakeStore()
    svc = service(store, FakeProfiles())
    mission_id = svc.snapshot(17)["mission"]["id"]
    svc.accept(17, mission_id)
    result = svc.complete(
        17,
        mission_id,
        outcome="mixed",
        metrics={
            "clean_executions": 99999,
            "rotation_timing_ms": -99999999,
            "death_cause": "x" * 500,
            "server_admin": 1,
        },
    )
    metrics = result["session"]["last_review"]["metrics"]
    assert metrics["clean_executions"] == 100
    assert metrics["rotation_timing_ms"] == -600000
    assert len(metrics["death_cause"]) == 240
    assert "server_admin" not in metrics
