from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.crown_core.actions import ActionValidationFailure, CrownActionRegistry
from app.crown_core.contracts import CrownPrincipal


ACTION_RESULT_PROTOCOL_VERSION = "crown-actions-v1"
_ALLOWED_MEMORY_FIELDS = {"current_goal", "training_focus", "weekly_focus", "playstyle"}
_ALLOWED_DESTINATIONS = {"live", "war_room", "analyze", "brain", "history", "settings"}


class CrownActionResultFailure(ValueError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "invalid_action_result")[:80]
        super().__init__(self.code)


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

    if clean["action_id"] == "analyze.open_report":
        report_id = clean["result"].get("report_id")
        if not report_id or core.analysis_report(principal, report_id) is None:
            raise CrownActionResultFailure("analysis_report_not_found")

    episodes = list(core.store.list_episodes(principal.legacy_owner_id, 100) or [])
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
