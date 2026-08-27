from uuid import uuid4

import pytest

from app.crown_core.action_stream import (
    proposals_from_provider_metadata,
    realtime_action_payload,
)
from app.crown_core.actions import ActionValidationFailure


def _proposal(action_id: str, arguments: dict) -> dict:
    return {
        "proposal_id": str(uuid4()),
        "action_id": action_id,
        "arguments": arguments,
        "rationale": "bounded test rationale",
        "correlation_id": str(uuid4()),
    }


def test_realtime_action_payload_is_crown_native_and_versioned() -> None:
    turn_id = uuid4()
    (proposal,) = proposals_from_provider_metadata(
        {"action_proposals": [_proposal("app.navigate", {"destination": "brain"})]},
        source_turn_id=turn_id,
    )
    payload = realtime_action_payload(proposal)
    assert payload["type"] == "actionProposal"
    assert payload["actionProposal"]["protocol_version"] == "crown-actions-v1"
    assert payload["actionProposal"]["source_turn_id"] == str(turn_id)
    assert payload["actionProposal"]["action_id"] == "app.navigate"


def test_empty_provider_metadata_produces_no_actions() -> None:
    assert proposals_from_provider_metadata(None, source_turn_id=uuid4()) == ()
    assert proposals_from_provider_metadata({}, source_turn_id=uuid4()) == ()


def test_unknown_action_fails_closed() -> None:
    with pytest.raises(ActionValidationFailure, match="unknown_action"):
        proposals_from_provider_metadata(
            {"action_proposals": [_proposal("shell.execute", {"command": "rm -rf /"})]},
            source_turn_id=uuid4(),
        )


def test_too_many_action_proposals_fail_closed() -> None:
    items = [_proposal("app.navigate", {"destination": "live"}) for _ in range(5)]
    with pytest.raises(ActionValidationFailure, match="too_many_action_proposals"):
        proposals_from_provider_metadata(
            {"action_proposals": items},
            source_turn_id=uuid4(),
            maximum=4,
        )


def test_duplicate_proposal_ids_fail_closed() -> None:
    item = _proposal("app.navigate", {"destination": "live"})
    with pytest.raises(ActionValidationFailure, match="duplicate_action_proposal"):
        proposals_from_provider_metadata(
            {"action_proposals": [item, dict(item)]},
            source_turn_id=uuid4(),
        )


def test_reminder_requires_structured_schedule() -> None:
    with pytest.raises(ActionValidationFailure, match="invalid_reminder"):
        proposals_from_provider_metadata(
            {
                "action_proposals": [
                    _proposal(
                        "reminder.create",
                        {"title": "Тренировка", "schedule": "tomorrow evening"},
                    )
                ]
            },
            source_turn_id=uuid4(),
        )
