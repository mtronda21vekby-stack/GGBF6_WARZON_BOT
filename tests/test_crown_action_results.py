from __future__ import annotations

from uuid import uuid4

import pytest

from app.crown_core.action_results import (
    CrownActionResultFailure,
    normalize_action_result,
    recent_action_results,
    record_action_result,
    record_issued_action_proposal,
)
from app.crown_core.actions import normalize_action_proposal
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


def proposal_and_result(action_id: str, arguments: dict, result: dict):
    proposal_id = uuid4()
    turn_id = uuid4()
    correlation_id = uuid4()
    proposal = normalize_action_proposal(
        {
            "proposal_id": str(proposal_id),
            "correlation_id": str(correlation_id),
            "action_id": action_id,
            "arguments": arguments,
            "rationale": "test",
        },
        source_turn_id=turn_id,
    )
    body = {
        "protocol_version": "crown-actions-v1",
        "proposal_id": str(proposal_id),
        "action_id": action_id,
        "source_turn_id": str(turn_id),
        "correlation_id": str(correlation_id),
        "status": "succeeded",
        "result": result,
    }
    return proposal, body


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


def test_issued_proposal_proof_omits_sensitive_free_form_arguments():
    core = FakeCore()
    user = principal(100)
    proposal, _body = proposal_and_result(
        "memory.propose_save",
        {"field": "current_goal", "value": "private long-term goal"},
        {"field": "current_goal"},
    )

    recorded = record_issued_action_proposal(core, user, proposal)
    assert recorded["expected_result"] == {"field": "current_goal"}
    assert "private long-term goal" not in repr(recorded)


def test_action_result_requires_server_issued_proposal():
    core = FakeCore()
    user = principal(101)
    _proposal, body = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )

    with pytest.raises(CrownActionResultFailure, match="action_proposal_not_issued"):
        record_action_result(core, user, body)


def test_action_result_is_owner_scoped_and_idempotent():
    core = FakeCore()
    first = principal(201)
    second = principal(202)
    proposal, body = proposal_and_result(
        "memory.propose_save",
        {"field": "current_goal", "value": "Top 250"},
        {"field": "current_goal"},
    )
    record_issued_action_proposal(core, first, proposal)

    one = record_action_result(core, first, body)
    replay = record_action_result(core, first, body)
    assert replay["proposal_id"] == one["proposal_id"]
    assert recent_action_results(core, first)[-1]["proposal_id"] == one["proposal_id"]
    assert recent_action_results(core, second) == []
    with pytest.raises(CrownActionResultFailure, match="action_proposal_not_issued"):
        record_action_result(core, second, body)


def test_result_payload_cannot_disagree_with_issued_proposal():
    core = FakeCore()
    user = principal(303)
    proposal, body = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    record_issued_action_proposal(core, user, proposal)

    conflicting = dict(body)
    conflicting["result"] = {"destination": "history"}
    with pytest.raises(CrownActionResultFailure, match="action_result_payload_mismatch"):
        record_action_result(core, user, conflicting)


def test_result_lineage_cannot_change_source_turn_or_correlation():
    core = FakeCore()
    user = principal(304)
    proposal, body = proposal_and_result(
        "memory.forget",
        {"field": "playstyle"},
        {"field": "playstyle"},
    )
    record_issued_action_proposal(core, user, proposal)

    tampered = dict(body)
    tampered["source_turn_id"] = str(uuid4())
    with pytest.raises(CrownActionResultFailure, match="action_result_lineage_mismatch"):
        record_action_result(core, user, tampered)


def test_analyze_result_requires_owner_scoped_report():
    core = FakeCore()
    user = principal(404)
    report_id = uuid4()
    proposal, body = proposal_and_result(
        "analyze.open_report",
        {"report_id": str(report_id)},
        {"report_id": str(report_id)},
    )
    record_issued_action_proposal(core, user, proposal)

    with pytest.raises(CrownActionResultFailure, match="analysis_report_not_found"):
        record_action_result(core, user, body)

    core.reports[user.legacy_owner_id] = {str(report_id)}
    recorded = record_action_result(core, user, body)
    assert recorded["result"] == {"report_id": str(report_id)}


def test_unknown_action_result_is_never_accepted():
    with pytest.raises(CrownActionResultFailure, match="unknown_action"):
        normalize_action_result(result_body("shell.execute", {}))
