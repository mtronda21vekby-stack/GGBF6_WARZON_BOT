from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.crown_core.action_results import (
    CrownActionResultFailure,
    normalize_action_result,
    recent_action_audit,
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
        self.profiles: dict[int, dict[str, str]] = {}

    def analysis_report(self, principal: CrownPrincipal, report_id):
        if str(report_id) in self.reports.get(principal.legacy_owner_id, set()):
            return {"id": str(report_id)}
        return None

    def profile_for(self, principal: CrownPrincipal):
        return dict(self.profiles.get(principal.legacy_owner_id, {}))


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


def outcome_body(proposal, *, status: str, failure_code: str | None = None, **extra):
    body = {
        "protocol_version": "crown-actions-v1",
        "proposal_id": str(proposal.proposal_id),
        "action_id": proposal.action_id,
        "source_turn_id": str(proposal.source_turn_id),
        "correlation_id": str(proposal.correlation_id),
        "status": status,
        "result": {"arbitrary": "must be stripped"},
        "detail": "private client prose must never enter canonical context",
        **extra,
    }
    if failure_code is not None:
        body["failure_code"] = failure_code
    return body


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


def test_non_success_result_keeps_only_closed_status_and_failure_code():
    proposal, _ = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    normalized = normalize_action_result(
        outcome_body(
            proposal,
            status="failed",
            failure_code="execution_failed",
            secret="do-not-store",
        )
    )
    assert normalized["status"] == "failed"
    assert normalized["failure_code"] == "execution_failed"
    assert normalized["result"] == {}
    assert "detail" not in normalized
    assert "secret" not in normalized


def test_non_success_failure_code_is_closed_allowlist():
    proposal, _ = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    with pytest.raises(CrownActionResultFailure, match="invalid_action_failure_code"):
        normalize_action_result(
            outcome_body(
                proposal,
                status="failed",
                failure_code="shell_output:/private/path",
            )
        )


def test_rejected_and_cancelled_have_deterministic_codes():
    proposal, _ = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    rejected = normalize_action_result(outcome_body(proposal, status="rejected"))
    cancelled = normalize_action_result(outcome_body(proposal, status="cancelled"))
    assert rejected["failure_code"] == "confirmation_rejected"
    assert cancelled["failure_code"] == "cancelled"


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
    assert recorded["risk"] == "reversible_write"
    assert recorded["confirmation"] == "required"
    assert recorded["effect_proof"]["field"] == "current_goal"
    assert len(recorded["effect_proof"]["value_digest"]) == 64
    assert "private long-term goal" not in repr(recorded)

    audit = recent_action_audit(core, user)
    assert [event["outcome"] for event in audit] == ["proposed", "validated"]


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


def test_non_success_result_also_requires_server_issued_proposal():
    core = FakeCore()
    user = principal(103)
    proposal, _ = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    with pytest.raises(CrownActionResultFailure, match="action_proposal_not_issued"):
        record_action_result(
            core,
            user,
            outcome_body(proposal, status="failed", failure_code="execution_failed"),
        )


def test_stale_unrecorded_action_result_is_rejected():
    core = FakeCore()
    user = principal(102)
    proposal, body = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    record_issued_action_proposal(core, user, proposal)
    issued = next(
        item["action_proposal"]
        for item in core.store.episodes[user.legacy_owner_id]
        if item.get("kind") == "action_proposal_issued"
    )
    issued["issued_at"] = (
        datetime.now(UTC) - timedelta(minutes=16)
    ).isoformat().replace("+00:00", "Z")

    with pytest.raises(CrownActionResultFailure, match="action_proposal_expired"):
        record_action_result(core, user, body)


def test_stale_non_success_outcome_is_rejected():
    core = FakeCore()
    user = principal(104)
    proposal, _ = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    record_issued_action_proposal(core, user, proposal)
    issued = next(
        item["action_proposal"]
        for item in core.store.episodes[user.legacy_owner_id]
        if item.get("kind") == "action_proposal_issued"
    )
    issued["issued_at"] = (
        datetime.now(UTC) - timedelta(minutes=16)
    ).isoformat().replace("+00:00", "Z")
    with pytest.raises(CrownActionResultFailure, match="action_proposal_expired"):
        record_action_result(
            core,
            user,
            outcome_body(proposal, status="cancelled"),
        )


def test_memory_save_result_requires_exact_canonical_effect():
    core = FakeCore()
    user = principal(201)
    proposal, body = proposal_and_result(
        "memory.propose_save",
        {"field": "current_goal", "value": "Top 250"},
        {"field": "current_goal"},
    )
    record_issued_action_proposal(core, user, proposal)

    core.profiles[user.legacy_owner_id] = {"current_goal": "Wrong value"}
    with pytest.raises(CrownActionResultFailure, match="action_effect_mismatch"):
        record_action_result(core, user, body)

    core.profiles[user.legacy_owner_id] = {"current_goal": "Top 250"}
    recorded = record_action_result(core, user, body)

    # Once the exact execution result has been accepted, replay remains
    # idempotent even if the user later edits that memory again.
    core.profiles[user.legacy_owner_id] = {"current_goal": "Changed later"}
    replay = record_action_result(core, user, body)
    assert replay["proposal_id"] == recorded["proposal_id"]
    assert recent_action_results(core, user)[-1]["proposal_id"] == recorded["proposal_id"]
    assert [event["outcome"] for event in recent_action_audit(core, user)] == [
        "proposed",
        "validated",
        "succeeded",
    ]


def test_non_success_outcomes_are_canonical_and_audited():
    cases = [
        ("denied", "unauthorized"),
        ("rejected", None),
        ("failed", "execution_failed"),
        ("cancelled", None),
    ]
    for offset, (status, failure_code) in enumerate(cases):
        core = FakeCore()
        user = principal(220 + offset)
        proposal, _ = proposal_and_result(
            "app.navigate",
            {"destination": "brain"},
            {"destination": "brain"},
        )
        record_issued_action_proposal(core, user, proposal)
        recorded = record_action_result(
            core,
            user,
            outcome_body(proposal, status=status, failure_code=failure_code),
        )
        assert recorded["status"] == status
        assert recorded["result"] == {}
        assert recent_action_results(core, user)[-1]["status"] == status
        assert [event["outcome"] for event in recent_action_audit(core, user)] == [
            "proposed",
            "validated",
            status,
        ]


def test_non_success_exact_replay_is_idempotent_but_status_flip_conflicts():
    core = FakeCore()
    user = principal(230)
    proposal, _ = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    record_issued_action_proposal(core, user, proposal)
    failed = outcome_body(proposal, status="failed", failure_code="execution_failed")
    first = record_action_result(core, user, failed)
    replay = record_action_result(core, user, failed)
    assert replay == first

    with pytest.raises(CrownActionResultFailure, match="action_result_conflict"):
        record_action_result(core, user, outcome_body(proposal, status="cancelled"))


def test_action_result_is_owner_scoped():
    core = FakeCore()
    first = principal(301)
    second = principal(302)
    proposal, body = proposal_and_result(
        "app.navigate",
        {"destination": "brain"},
        {"destination": "brain"},
    )
    record_issued_action_proposal(core, first, proposal)
    record_action_result(core, first, body)

    assert recent_action_results(core, first)
    assert recent_action_results(core, second) == []
    assert recent_action_audit(core, second) == []
    with pytest.raises(CrownActionResultFailure, match="action_proposal_not_issued"):
        record_action_result(core, second, body)


def test_memory_forget_result_requires_field_to_be_absent():
    core = FakeCore()
    user = principal(303)
    proposal, body = proposal_and_result(
        "memory.forget",
        {"field": "playstyle"},
        {"field": "playstyle"},
    )
    record_issued_action_proposal(core, user, proposal)

    core.profiles[user.legacy_owner_id] = {"playstyle": "aggressive"}
    with pytest.raises(CrownActionResultFailure, match="action_effect_mismatch"):
        record_action_result(core, user, body)

    core.profiles[user.legacy_owner_id] = {"playstyle": ""}
    recorded = record_action_result(core, user, body)
    assert recorded["result"] == {"field": "playstyle"}


def test_result_payload_cannot_disagree_with_issued_proposal():
    core = FakeCore()
    user = principal(304)
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
    user = principal(305)
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
