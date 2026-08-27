from uuid import uuid4

import pytest

from app.crown_core.actions import (
    ActionRisk,
    ActionValidationFailure,
    CrownActionRegistry,
    normalize_action_proposal,
)


def proposal(action_id: str, arguments: dict):
    return normalize_action_proposal(
        {
            "proposal_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "action_id": action_id,
            "arguments": arguments,
            "rationale": "test",
        },
        source_turn_id=uuid4(),
    )


def test_registry_is_closed_and_fixed():
    assert CrownActionRegistry.capabilities() == (
        "app.navigate",
        "memory.propose_save",
        "memory.forget",
        "reminder.create",
        "analyze.open_report",
    )
    assert CrownActionRegistry.definition("memory.forget").risk is ActionRisk.SENSITIVE_WRITE
    with pytest.raises(ActionValidationFailure, match="unknown_action"):
        CrownActionRegistry.definition("shell.exec")


def test_validation_failure_exposes_bounded_stable_code():
    with pytest.raises(ActionValidationFailure) as captured:
        CrownActionRegistry.definition("shell.exec")
    assert captured.value.code == "unknown_action"
    assert str(captured.value) == "unknown_action"


def test_navigation_rejects_arbitrary_destinations():
    assert proposal("app.navigate", {"destination": "brain"}).arguments == {"destination": "brain"}
    with pytest.raises(ActionValidationFailure, match="invalid_destination"):
        proposal("app.navigate", {"destination": "https://example.com"})


def test_memory_is_allowlisted_and_bounded_to_canonical_patch_contract():
    normalized = proposal(
        "memory.propose_save",
        {"field": "current_goal", "value": "Тренироваться каждый день"},
    )
    assert normalized.arguments["field"] == "current_goal"
    assert len(proposal(
        "memory.propose_save",
        {"field": "current_goal", "value": "x" * 240},
    ).arguments["value"]) == 240
    with pytest.raises(ActionValidationFailure, match="invalid_memory_proposal"):
        proposal("memory.propose_save", {"field": "service_role_key", "value": "x"})
    with pytest.raises(ActionValidationFailure, match="invalid_memory_proposal"):
        proposal("memory.propose_save", {"field": "current_goal", "value": "x" * 241})


def test_forget_rejects_unknown_memory_target():
    assert proposal("memory.forget", {"field": "playstyle"}).arguments == {"field": "playstyle"}
    with pytest.raises(ActionValidationFailure, match="invalid_memory_target"):
        proposal("memory.forget", {"field": "account"})


def test_reminder_schedule_is_structured_not_free_form():
    normalized = proposal(
        "reminder.create",
        {
            "title": "Тренировка",
            "schedule": {"kind": "relative", "seconds": 7200},
        },
    )
    assert normalized.arguments["schedule"] == {"kind": "relative", "seconds": 7200}
    with pytest.raises(ActionValidationFailure, match="invalid_reminder_schedule"):
        proposal(
            "reminder.create",
            {"title": "Тренировка", "schedule": {"kind": "whenever", "text": "tomorrow"}},
        )


def test_analyze_report_requires_uuid():
    report_id = uuid4()
    assert proposal("analyze.open_report", {"report_id": str(report_id)}).arguments == {
        "report_id": str(report_id)
    }
    with pytest.raises(ActionValidationFailure, match="invalid_report_id"):
        proposal("analyze.open_report", {"report_id": "other-user-report"})


def test_arbitrary_execution_surface_is_not_a_capability():
    for blocked in ("shell.exec", "network.request", "url.open", "finance.transfer"):
        with pytest.raises(ActionValidationFailure, match="unknown_action"):
            proposal(blocked, {})
