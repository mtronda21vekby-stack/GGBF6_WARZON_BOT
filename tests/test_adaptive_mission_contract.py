from __future__ import annotations

import pytest

from app.services.missions.service import AdaptiveMissionService, MissionConflict
from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


def _service(chat_id: int = 7):
    store = InMemoryStore()
    profiles = ProfileService(store)
    profiles.patch(chat_id, {
        "game": "Warzone",
        "input": "Controller",
        "difficulty": "Pro",
        "training_focus": "positioning",
    })
    return store, profiles, AdaptiveMissionService(store=store, profiles=profiles), chat_id


def test_candidate_is_deterministic_and_evidence_backed():
    store, profiles, service, chat_id = _service()
    store.add_recurring_mistake(chat_id, "Поздняя ротация")
    store.add_recurring_mistake(chat_id, "Поздняя ротация")

    first = service.snapshot(chat_id)
    second = service.snapshot(chat_id)

    assert first["mission"]["id"] == second["mission"]["id"]
    assert first["mission"]["status"] == "candidate"
    assert first["mission"]["focus"] == "positioning"
    assert first["mission"]["evidence"]
    assert len(first["mission"]["protocol"]) == 3


def test_accept_is_idempotent_and_only_one_mission_is_active():
    store, profiles, service, chat_id = _service()
    candidate = service.snapshot(chat_id)["mission"]

    accepted = service.accept(chat_id, candidate["id"])
    accepted_again = service.accept(chat_id, candidate["id"])

    assert accepted["mission"]["status"] == "active"
    assert accepted_again["mission"]["id"] == candidate["id"]
    mission_events = [
        row for row in store.list_progression_events(chat_id)
        if row.get("type") == "adaptive_mission" and row.get("status") == "accepted"
    ]
    assert len(mission_events) == 1


def test_stale_mission_identifier_is_rejected():
    _, _, service, chat_id = _service()
    with pytest.raises(MissionConflict):
        service.accept(chat_id, "m19-foreign")


def test_completion_records_bounded_outcome_and_unlocks_next_cycle():
    store, profiles, service, chat_id = _service()
    candidate = service.snapshot(chat_id)["mission"]
    service.accept(chat_id, candidate["id"])

    completed = service.complete(
        chat_id,
        candidate["id"],
        outcome="clean",
        metrics={"kills": 9, "accuracy_pct": 63.5, "unknown": 999},
        note="Ротации начал раньше и не умер в газе.",
    )

    assert completed["completion"]["outcome"] == "clean"
    assert completed["completion"]["metrics"]["kills"] == 9
    assert completed["completion"]["metrics"]["accuracy_pct"] == 63.5
    assert "unknown" not in completed["completion"]["metrics"]
    assert completed["mission"]["status"] == "candidate"
    assert completed["mission"]["id"] != candidate["id"]
    events = store.list_progression_events(chat_id)
    assert any(row.get("status") == "completed" and row.get("mission_id") == candidate["id"] for row in events)
