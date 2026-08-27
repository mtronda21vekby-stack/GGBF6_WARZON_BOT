from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.crown_core.actions import (
    ActionValidationFailure,
    CrownActionProposal,
    CrownActionRegistry,
)
from app.crown_core.contracts import CrownPrincipal


ACTION_RESULT_PROTOCOL_VERSION = "crown-actions-v1"
_ALLOWED_MEMORY_FIELDS = {"current_goal", "training_focus", "weekly_focus", "playstyle"}
_ALLOWED_DESTINATIONS = {"live", "war_room", "analyze", "brain", "history", "settings"}


class CrownActionResultFailure(ValueError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "invalid_action_result")[:80]
        super().__init__(self.code)


def record_issued_action_proposal(
    core: Any,
    principal: CrownPrincipal,
    proposal: CrownActionProposal,
) -> dict[str, Any]:
    """Persist a privacy-bounded proof that this proposal was server-issued.

    The proof deliberately omits memory values, reminder titles/notes and other
    free-form proposal content. It exists solely to prevent a compromised or
    buggy client from fabricating a successful action that CROWN never proposed.
    """

    issued = {
        "protocol_version": ACTION_RESULT_PROTOCOL_VERSION,
        "proposal_id": str(proposal.proposal_id),
        "action_id": str(proposal.action_id),
        "source_turn_id": str(proposal.source_turn_id),
        "correlation_id": str(proposal.correlation_id),
        "expected_result": _expected_result(proposal),
    }

    episodes = list(core.store.list_episodes(principal.legacy_owner_id, 100) or [])
    for item in episodes:
        if not isinstance(item, dict) or item.get("kind") != "action_proposal_issued":
            continue
        existing = item.get("action_proposal")
        if not isinstance(existing, dict):
            continue
        if str(existing.get("proposal_id") or "") != issued["proposal_id"]:
            continue
        comparable = {key: existing.get(key) for key in issued}
        if comparable != issued:
            raise CrownActionResultFailure("action_proposal_conflict")
        return dict(existing)

    recorded = {
        **issued,
        "issued_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    core.store.add_episode(
        principal.legacy_owner_id,
        {"kind": "action_proposal_issued", "action_proposal": recorded},
    )
    return recorded


def normalize_action_result(raw: Any) -> dict[str, Any]:
    """Validate device execution truth before it enters canonical context.

    The device may report only the outcome of a server-known action proposal.
    Raw EventKit identifiers, arbitrary text, secrets and provider metadata are
    intentionally excluded from this projection.
    """

    if not isinstance(raw, dict):
        raise CrownActionResultFailure("invalid_action_result")
    if str(raw.get("protocol_version") or "") != ACTION_RESULT_PROTOCOL_VERSION:
        raise CrownActionResultFailure("action_protocol_mismatch")

    try:
        proposal_id = UUID(str(raw.get("proposal_id") or ""))
        source_turn_id = UUID(str(raw.get("source_turn_id") or ""))
        correlation_id = UUID(str(raw.get("correlation_id") or ""))
    except ValueError:
        raise CrownActionResultFailure("invalid_action_result_identifier") from None

    action_id = str(raw.get("action_id") or "").strip()
    try:
        CrownActionRegistry.definition(action_id)
    except ActionValidationFailure as failure:
        raise CrownActionResultFailure(failure.code) from None
    if str(raw.get("status") or "") != "succeeded":
        raise CrownActionResultFailure("unsupported_action_result_status")

    payload = _normalize_payload(action_id, raw.get("result"))
    return {
        "protocol_version": ACTION_RESULT_PROTOCOL_VERSION,
        "proposal_id": str(proposal_id),
        "action_id": action_id,
        "source_turn_id": str(source_turn_id),
        "correlation_id": str(correlation_id),
        "status": "succeeded",
        "result": payload,
    }


def record_action_result(
    core: Any,
    principal: CrownPrincipal,
    raw: Any,
) -> dict[str, Any]:
    clean = normalize_action_result(raw)
    episodes = list(core.store.list_episodes(principal.legacy_owner_id, 100) or [])
    issued = _find_issued_proposal(episodes, clean["proposal_id"])
    if issued is None:
        raise CrownActionResultFailure("action_proposal_not_issued")
    _validate_lineage(clean, issued)

    if clean["action_id"] == "analyze.open_report":
        report_id = clean["result"].get("report_id")
        if not report_id or core.analysis_report(principal, report_id) is None:
            raise CrownActionResultFailure("analysis_report_not_found")

    for item in episodes:
        if not isinstance(item, dict) or item.get("kind") != "action_result":
            continue
        existing = item.get("action_result")
        if not isinstance(existing, dict):
            continue
        if str(existing.get("proposal_id") or "") != clean["proposal_id"]:
            continue
        comparable = {key: existing.get(key) for key in clean}
        if comparable != clean:
            raise CrownActionResultFailure("action_result_conflict")
        return dict(existing)

    recorded = {
        **clean,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    core.store.add_episode(
        principal.legacy_owner_id,
        {"kind": "action_result", "action_result": recorded},
    )
    return recorded


def recent_action_results(
    core: Any,
    principal: CrownPrincipal,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    bounded = max(1, min(int(limit), 8))
    episodes = list(core.store.list_episodes(principal.legacy_owner_id, 100) or [])
    results: list[dict[str, Any]] = []
    for item in episodes:
        if not isinstance(item, dict) or item.get("kind") != "action_result":
            continue
        value = item.get("action_result")
        if not isinstance(value, dict):
            continue
        try:
            clean = normalize_action_result(value)
        except CrownActionResultFailure:
            continue
        results.append(
            {
                **clean,
                "recorded_at": str(value.get("recorded_at") or "")[:40],
            }
        )
    return results[-bounded:]


def _expected_result(proposal: CrownActionProposal) -> dict[str, Any]:
    arguments = dict(proposal.arguments or {})
    if proposal.action_id == "app.navigate":
        return {"destination": str(arguments.get("destination") or "")}
    if proposal.action_id in {"memory.propose_save", "memory.forget"}:
        return {"field": str(arguments.get("field") or "")}
    if proposal.action_id == "analyze.open_report":
        return {"report_id": str(arguments.get("report_id") or "")}
    if proposal.action_id == "reminder.create":
        # The final instant is device-resolved from local Calendar/TimeZone, so
        # there is no safe server-side equality assertion for scheduled_at.
        return {}
    raise CrownActionResultFailure("unknown_action")


def _find_issued_proposal(
    episodes: list[Any],
    proposal_id: str,
) -> dict[str, Any] | None:
    for item in reversed(episodes):
        if not isinstance(item, dict) or item.get("kind") != "action_proposal_issued":
            continue
        issued = item.get("action_proposal")
        if isinstance(issued, dict) and str(issued.get("proposal_id") or "") == proposal_id:
            return dict(issued)
    return None


def _validate_lineage(clean: dict[str, Any], issued: dict[str, Any]) -> None:
    for key in ("protocol_version", "proposal_id", "action_id", "source_turn_id", "correlation_id"):
        if str(clean.get(key) or "") != str(issued.get(key) or ""):
            raise CrownActionResultFailure("action_result_lineage_mismatch")

    expected = issued.get("expected_result")
    if not isinstance(expected, dict):
        raise CrownActionResultFailure("action_result_lineage_invalid")
    for key, expected_value in expected.items():
        if clean["result"].get(key) != expected_value:
            raise CrownActionResultFailure("action_result_payload_mismatch")


def _normalize_payload(action_id: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CrownActionResultFailure("invalid_action_result_payload")

    if action_id == "app.navigate":
        destination = str(value.get("destination") or "").strip()
        if destination not in _ALLOWED_DESTINATIONS:
            raise CrownActionResultFailure("invalid_destination")
        return {"destination": destination}

    if action_id == "memory.propose_save":
        field = str(value.get("field") or "").strip()
        if field not in _ALLOWED_MEMORY_FIELDS:
            raise CrownActionResultFailure("invalid_memory_result")
        return {"field": field}

    if action_id == "memory.forget":
        field = str(value.get("field") or "").strip()
        if field not in _ALLOWED_MEMORY_FIELDS:
            raise CrownActionResultFailure("invalid_memory_result")
        return {"field": field}

    if action_id == "reminder.create":
        scheduled_at = str(value.get("scheduled_at") or "").strip()
        if not scheduled_at or len(scheduled_at) > 64:
            raise CrownActionResultFailure("invalid_reminder_result")
        return {"scheduled_at": scheduled_at}

    if action_id == "analyze.open_report":
        try:
            report_id = UUID(str(value.get("report_id") or ""))
        except ValueError:
            raise CrownActionResultFailure("invalid_report_id") from None
        return {"report_id": str(report_id)}

    raise CrownActionResultFailure("unknown_action")
