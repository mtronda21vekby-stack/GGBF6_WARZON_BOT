from __future__ import annotations

from typing import Any
from uuid import UUID

from app.crown_core.actions import (
    ACTION_PROTOCOL_VERSION,
    ActionValidationFailure,
    CrownActionProposal,
    normalize_action_proposal,
)


REALTIME_EVENT_TYPE = "actionProposal"


def normalize_provider_action_event(
    raw: dict[str, Any],
    *,
    source_turn_id: UUID,
) -> CrownActionProposal:
    """Convert untrusted provider metadata into one bounded CROWN-native proposal."""
    return normalize_action_proposal(raw, source_turn_id=source_turn_id)


def realtime_action_payload(proposal: CrownActionProposal) -> dict[str, Any]:
    """Projection embedded inside crown-realtime-v1 SSE envelopes."""
    projection = proposal.projection()
    if projection.get("protocol_version") != ACTION_PROTOCOL_VERSION:
        raise ActionValidationFailure("protocol_mismatch")
    return {
        "type": REALTIME_EVENT_TYPE,
        "actionProposal": projection,
    }


def proposals_from_provider_metadata(
    metadata: Any,
    *,
    source_turn_id: UUID,
    maximum: int = 4,
) -> tuple[CrownActionProposal, ...]:
    """
    Fail closed over optional provider metadata.

    Existing providers may emit no structured action metadata at all. That is valid and
    returns an empty tuple. Unknown or malformed proposals are rejected instead of being
    surfaced to a device executor.
    """
    if metadata is None:
        return ()
    if not isinstance(metadata, dict):
        raise ActionValidationFailure("invalid_action_metadata")
    raw_items = metadata.get("action_proposals")
    if raw_items is None:
        return ()
    if not isinstance(raw_items, list):
        raise ActionValidationFailure("invalid_action_metadata")
    if len(raw_items) > max(1, min(int(maximum), 8)):
        raise ActionValidationFailure("too_many_action_proposals")
    proposals: list[CrownActionProposal] = []
    seen: set[UUID] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ActionValidationFailure("invalid_action_proposal")
        proposal = normalize_provider_action_event(raw, source_turn_id=source_turn_id)
        if proposal.proposal_id in seen:
            raise ActionValidationFailure("duplicate_action_proposal")
        seen.add(proposal.proposal_id)
        proposals.append(proposal)
    return tuple(proposals)
