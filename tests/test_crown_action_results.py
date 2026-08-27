from __future__ import annotations

from uuid import uuid4

import pytest

from app.crown_core.action_results import (
    CrownActionResultFailure,
    normalize_action_result,
    recent_action_results,
    record_action_result,
)
from app.crown_core.contracts import CrownPrincipal


class FakeStore:
    def __init__(self):
        self.episodes: dict[int, list[dict]] = {}

    def list_episodes(self, owner_id: int, _limit: int):
        return list(self.episodes.get(owner_id, []))

    def add_episode(self, owner_id: int, episode: dict):
        self.episodes.setdefault(owner_id, []).append(dict(episode))


class FakeCore:
    def __init__(self):
        self.store = FakeStore()
        self.reports: dict[int, set[str]] = {}

    def analysis_report(self, principal: CrownPrincipal, report_id):
        if str(report_id) in self.reports.get(principal.legacy_owner_id, set()):
            return {"id": str(report_id)}
        return None


def principal(owner_id: int) -> CrownPrincipal:
    return CrownPrincipal(uuid4(), "apple", str(uuid4()), owner_id)


def result_body(action_id: str, result: dict, *, proposal_id=None):
    return {
        "protocol_version": "crown-actions-v1",
        "proposal_id": str(proposal_id or uuid4()),
        "action_id": action_id,
        "source_turn_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "status": "succeeded",
        "result": result,
    }


def test_reminder_result_strips_device_identifier_and_arbitrary_text():
    body = result_body(
        "reminder.create",
        {
            "scheduled_at": "2026-08-28T20:00:00-04:00",
            "identifier": "EKReminder-private-id",
            "title": "private title must not enter canonical result context",
        },
    )
    normalized = normalize_action_result(body)
    assert normalized["result"] == {"scheduled_at": "2026-08-28T20:00:00-04:00"}


def test_action_result_is_owner_scoped_and_idempotent():
    core = FakeCore()
    first = principal(101)
    second = principal(202)
    proposal_id = uuid4()
    body = result_body(
        "memory.propose_save",
        {"field": "current_goal"},
        proposal_id=proposal_id,
    )

    one = record_action_result(core, first, body)
    replay = record_action_result(core, first, body)
    assert replay["proposal_id"] == one["proposal_id"]
    assert len(core.store.episodes[101]) == 1
    assert recent_action_results(core, second) == []


def test_conflicting_replay_fails_closed():
    core = FakeCore()
    user = principal(303)
    proposal_id = uuid4()
    first = result_body(
        "app.navigate",
        {"destination": "brain"},
        proposal_id=proposal_id,
    )
    record_action_result(core, user, first)

    conflicting = dict(first)
    conflicting["result"] = {"destination": "history"}
    with pytest.raises(CrownActionResultFailure, match="action_result_conflict"):
        record_action_result(core, user, conflicting)


def test_analyze_result_requires_owner_scoped_report():
    core = FakeCore()
    user = principal(404)
    report_id = uuid4()
    body = result_body(
        "analyze.open_report",
        {"report_id": str(report_id)},
    )

    with pytest.raises(CrownActionResultFailure, match="analysis_report_not_found"):
        record_action_result(core, user, body)

    core.reports[user.legacy_owner_id] = {str(report_id)}
    recorded = record_action_result(core, user, body)
    assert recorded["result"] == {"report_id": str(report_id)}


def test_unknown_action_result_is_never_accepted():
    with pytest.raises(Exception):
        normalize_action_result(result_body("shell.execute", {}))
