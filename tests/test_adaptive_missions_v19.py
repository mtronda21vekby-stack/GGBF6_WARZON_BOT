from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from app.services.missions.service import AdaptiveMissionService, MissionConflict
from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


def _service(chat_id: int = 77):
    store = InMemoryStore()
    profiles = ProfileService(store)
    profile = profiles.get(chat_id)
    return AdaptiveMissionService(store=store, profiles=profiles), store, profiles, profile


def _call(service, names, *args, **kwargs):
    for name in names:
        fn = getattr(service, name, None)
        if callable(fn):
            signature = inspect.signature(fn)
            accepted = {
                key: value
                for key, value in kwargs.items()
                if key in signature.parameters
                or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values())
            }
            return fn(*args, **accepted)
    raise AssertionError(f"None of the mission methods exists: {names}")


def _candidate(service, chat_id, profile):
    return _call(
        service,
        ("snapshot", "get_snapshot", "mission_snapshot", "candidate", "get_candidate"),
        chat_id,
        profile=profile,
    )


def _mission_payload(snapshot):
    assert isinstance(snapshot, dict)
    mission = snapshot.get("mission") if isinstance(snapshot.get("mission"), dict) else snapshot
    assert isinstance(mission, dict)
    assert mission.get("id")
    assert mission.get("title")
    assert mission.get("focus") in {"aim", "movement", "positioning", "decision", "comms"}
    assert mission.get("objective")
    assert mission.get("protocol")
    assert mission.get("success_metric")
    return mission


def test_candidate_is_deterministic_and_measurable():
    service, store, profiles, profile = _service()
    first = _candidate(service, 77, profile)
    second = _candidate(service, 77, profile)
    one = _mission_payload(first)
    two = _mission_payload(second)

    assert one["id"] == two["id"]
    assert one["focus"] == two["focus"]
    assert int(one.get("duration_min") or 0) > 0
    assert one.get("game")
    assert one.get("input")


def test_accept_complete_and_idempotent_snapshot_cycle():
    service, store, profiles, profile = _service()
    mission = _mission_payload(_candidate(service, 77, profile))

    accepted = _call(
        service,
        ("accept", "accept_mission"),
        77,
        mission["id"],
        profile=profile,
    )
    accepted_mission = _mission_payload(accepted)
    assert accepted_mission["id"] == mission["id"]
    assert str(accepted_mission.get("status") or "").casefold() in {"accepted", "active", "in_progress"}

    completed = _call(
        service,
        ("complete", "complete_mission"),
        77,
        mission["id"],
        profile=profile,
        success=True,
        report={"success": True, "score": 1, "note": "protocol complete"},
        result={"success": True, "score": 1, "note": "protocol complete"},
        note="protocol complete",
    )
    assert isinstance(completed, dict)
    completed_mission = completed.get("mission") if isinstance(completed.get("mission"), dict) else completed
    assert str(completed_mission.get("status") or "").casefold() in {"completed", "complete", "done", "success"}

    refreshed = _candidate(service, 77, profile)
    refreshed_mission = _mission_payload(refreshed)
    assert refreshed_mission["id"] != ""


def test_stale_or_foreign_mission_id_cannot_mutate_active_state():
    service, store, profiles, profile = _service()
    mission = _mission_payload(_candidate(service, 77, profile))

    with pytest.raises((MissionConflict, ValueError, KeyError)):
        _call(
            service,
            ("accept", "accept_mission"),
            77,
            "foreign-mission-id",
            profile=profile,
        )

    current = _mission_payload(_candidate(service, 77, profile))
    assert current["id"] == mission["id"]


def test_service_does_not_require_a_paid_provider_or_secret_in_constructor():
    signature = inspect.signature(AdaptiveMissionService)
    names = set(signature.parameters)
    assert "api_key" not in names
    assert "openai_api_key" not in names
    assert "token" not in names
