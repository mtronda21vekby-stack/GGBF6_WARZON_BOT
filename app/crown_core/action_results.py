from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.crown_core.actions import (
    ActionValidationFailure,
    CrownActionProposal,
    CrownActionRegistry,
)
from app.crown_core.contracts import CrownPrincipal


ACTION_RESULT_PROTOCOL_VERSION = "crown-actions-v1"
ACTION_RESULT_ISSUANCE_TTL_SECONDS = 15 * 60
ACTION_RESULT_CLOCK_SKEW_SECONDS = 30
_ALLOWED_MEMORY_FIELDS = {"current_goal", "training_focus", "weekly_focus", "playstyle"}
_ALLOWED_DESTINATIONS = {"live", "war_room", "analyze", "brain", "history", "settings"}
_ALLOWED_STATUSES = {"succeeded", "denied", "rejected", "failed", "cancelled"}
_ALLOWED_FAILURE_CODES = {
    "unknown_action",
    "invalid_arguments",
    "unauthorized",
    "entitlement_required",
    "permission_denied",
    "permission_unavailable",
    "confirmation_required",
    "confirmation_rejected",
    "stale_proposal",
    "execution_failed",
    "idempotency_conflict",
    "cancelled",
    "prohibited_action",
}


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

    The proof deliberately omits raw memory values, reminder titles/notes and
    other free-form proposal content. Memory writes carry only a salted digest
    so a later device success cannot be accepted unless canonical state really
    matches the proposal that CROWN issued.
    """

    definition = CrownActionRegistry.definition(proposal.action_id)
    issued = {
        "protocol_version": ACTION_RESULT_PROTOCOL_VERSION,
        "proposal_id": str(proposal.proposal_id),
        "action_id": str(proposal.action_id),
        "source_turn_id": str(proposal.source_turn_id),
        "correlation_id": str(proposal.correlation_id),
        "risk": definition.risk.value,
        "confirmation": definition.confirmation.value,
        "expected_result": _expected_result(proposal),
        "effect_proof": _effect_proof(proposal),
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
        "issued_at": _now(),
    }
    core.store.add_episode(
        principal.legacy_owner_id,
        {"kind": "action_proposal_issued", "action_proposal": recorded},
    )
    _record_server_audit(core, principal, recorded, "proposed")
    _record_server_audit(core, principal, recorded, "validated")
    return recorded


def normalize_action_result(raw: Any) -> dict[str, Any]:
    """Validate device execution truth before it enters canonical context.

    Success carries only action-specific deterministic result fields. Denied,
    rejected, failed and cancelled outcomes carry only a closed failure code;
    arbitrary client prose, raw EventKit identifiers and provider metadata are
    never admitted into canonical context.
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

    status = str(raw.get("status") or "").strip()
    if status not in _ALLOWED_STATUSES:
        raise CrownActionResultFailure("unsupported_action_result_status")

    clean: dict[str, Any] = {
        "protocol_version": ACTION_RESULT_PROTOCOL_VERSION,
        "proposal_id": str(proposal_id),
        "action_id": action_id,
        "source_turn_id": str(source_turn_id),
        "correlation_id": str(correlation_id),
        "status": status,
    }
    if status == "succeeded":
        clean["result"] = _normalize_payload(action_id, raw.get("result"))
        return clean

    raw_code = str(raw.get("failure_code") or "").strip().lower()
    if status == "rejected":
        failure_code = raw_code or "confirmation_rejected"
        if failure_code != "confirmation_rejected":
            raise CrownActionResultFailure("invalid_action_failure_code")
    elif status == "cancelled":
        failure_code = raw_code or "cancelled"
        if failure_code != "cancelled":
            raise CrownActionResultFailure("invalid_action_failure_code")
    else:
        failure_code = raw_code
        if failure_code not in _ALLOWED_FAILURE_CODES:
            raise CrownActionResultFailure("invalid_action_failure_code")

    clean["failure_code"] = failure_code
    clean["result"] = {}
    return clean


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

    # An already-recorded identical outcome is an idempotent replay. Return it
    # before re-checking mutable current state or proposal freshness: a later
    # user edit must not turn a previously accepted execution into a conflict.
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

    _validate_issuance_freshness(issued)

    if clean["status"] == "succeeded":
        _validate_effect(core, principal, clean, issued)
        if clean["action_id"] == "analyze.open_report":
            report_id = clean["result"].get("report_id")
            if not report_id or core.analysis_report(principal, report_id) is None:
                raise CrownActionResultFailure("analysis_report_not_found")

    recorded = {
        **clean,
        "recorded_at": _now(),
    }
    core.store.add_episode(
        principal.legacy_owner_id,
        {"kind": "action_result", "action_result": recorded},
    )
    _record_server_audit(core, principal, issued, clean["status"])
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


def recent_action_audit(
    core: Any,
    principal: CrownPrincipal,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return privacy-bounded canonical action lifecycle metadata."""

    bounded = max(1, min(int(limit), 40))
    episodes = list(core.store.list_episodes(principal.legacy_owner_id, 100) or [])
    values: list[dict[str, Any]] = []
    for item in episodes:
        if not isinstance(item, dict) or item.get("kind") != "action_audit":
            continue
        event = item.get("action_audit")
        if not isinstance(event, dict):
            continue
        values.append(
            {
                "proposal_id": str(event.get("proposal_id") or ""),
                "action_id": str(event.get("action_id") or ""),
                "source_turn_id": str(event.get("source_turn_id") or ""),
                "correlation_id": str(event.get("correlation_id") or ""),
                "risk": str(event.get("risk") or ""),
                "confirmation": str(event.get("confirmation") or ""),
                "outcome": str(event.get("outcome") or ""),
                "recorded_at": str(event.get("recorded_at") or "")[:40],
            }
        )
    return values[-bounded:]


def _expected_result(proposal: CrownActionProposal) -> dict[str, Any]:
    arguments = dict(proposal.arguments or {})
    if proposal.action_id == "app.navigate":
        return {"destination": str(arguments.get("destination") or "")}
    if proposal.action_id in {"memory.propose_save", "memory.forget"}:
        return {"field": str(arguments.get("field") or "")}
    if proposal.action_id == "analyze.open_report":
        return {"report_id": str(arguments.get("report_id") or "")}
    if proposal.action_id == "reminder.create":
        return {}
    raise CrownActionResultFailure("unknown_action")


def _effect_proof(proposal: CrownActionProposal) -> dict[str, Any]:
    arguments = dict(proposal.arguments or {})
    if proposal.action_id == "memory.propose_save":
        field = str(arguments.get("field") or "")
        value = str(arguments.get("value") or "").strip()
        return {
            "field": field,
            "value_digest": _value_digest(str(proposal.proposal_id), value),
        }
    if proposal.action_id == "memory.forget":
        return {
            "field": str(arguments.get("field") or ""),
            "expects_absent": True,
        }
    return {}


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

    if clean.get("status") != "succeeded":
        return
    expected = issued.get("expected_result")
    if not isinstance(expected, dict):
        raise CrownActionResultFailure("action_result_lineage_invalid")
    result = clean.get("result")
    if not isinstance(result, dict):
        raise CrownActionResultFailure("invalid_action_result_payload")
    for key, expected_value in expected.items():
        if result.get(key) != expected_value:
            raise CrownActionResultFailure("action_result_payload_mismatch")


def _validate_issuance_freshness(issued: dict[str, Any]) -> None:
    raw = str(issued.get("issued_at") or "").strip()
    if not raw:
        raise CrownActionResultFailure("action_proposal_issued_at_missing")
    try:
        issued_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise CrownActionResultFailure("action_proposal_issued_at_invalid") from None
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if issued_at > now + timedelta(seconds=ACTION_RESULT_CLOCK_SKEW_SECONDS):
        raise CrownActionResultFailure("action_proposal_issued_at_invalid")
    if now - issued_at > timedelta(seconds=ACTION_RESULT_ISSUANCE_TTL_SECONDS):
        raise CrownActionResultFailure("action_proposal_expired")


def _validate_effect(
    core: Any,
    principal: CrownPrincipal,
    clean: dict[str, Any],
    issued: dict[str, Any],
) -> None:
    action_id = clean["action_id"]
    if action_id not in {"memory.propose_save", "memory.forget"}:
        return

    effect = issued.get("effect_proof")
    if not isinstance(effect, dict):
        raise CrownActionResultFailure("action_effect_proof_missing")
    profile_for = getattr(core, "profile_for", None)
    if not callable(profile_for):
        raise CrownActionResultFailure("action_effect_verification_unavailable")
    profile = profile_for(principal)
    if not isinstance(profile, dict):
        raise CrownActionResultFailure("action_effect_verification_unavailable")

    field = str(effect.get("field") or "")
    if field not in _ALLOWED_MEMORY_FIELDS:
        raise CrownActionResultFailure("action_effect_proof_invalid")
    actual = str(profile.get(field) or "").strip()

    if action_id == "memory.propose_save":
        expected_digest = str(effect.get("value_digest") or "")
        actual_digest = _value_digest(clean["proposal_id"], actual)
        if not expected_digest or actual_digest != expected_digest:
            raise CrownActionResultFailure("action_effect_mismatch")
        return

    if actual:
        raise CrownActionResultFailure("action_effect_mismatch")


def _record_server_audit(
    core: Any,
    principal: CrownPrincipal,
    issued: dict[str, Any],
    outcome: str,
) -> None:
    if outcome not in {"proposed", "validated", "succeeded", "denied", "rejected", "failed", "cancelled"}:
        raise CrownActionResultFailure("invalid_server_audit_outcome")
    event = {
        "proposal_id": str(issued.get("proposal_id") or ""),
        "action_id": str(issued.get("action_id") or ""),
        "source_turn_id": str(issued.get("source_turn_id") or ""),
        "correlation_id": str(issued.get("correlation_id") or ""),
        "risk": str(issued.get("risk") or ""),
        "confirmation": str(issued.get("confirmation") or ""),
        "outcome": outcome,
    }
    episodes = list(core.store.list_episodes(principal.legacy_owner_id, 100) or [])
    for item in episodes:
        if not isinstance(item, dict) or item.get("kind") != "action_audit":
            continue
        existing = item.get("action_audit")
        if not isinstance(existing, dict):
            continue
        if (
            str(existing.get("proposal_id") or "") == event["proposal_id"]
            and str(existing.get("outcome") or "") == outcome
        ):
            comparable = {key: existing.get(key) for key in event}
            if comparable != event:
                raise CrownActionResultFailure("action_audit_conflict")
            return
    core.store.add_episode(
        principal.legacy_owner_id,
        {"kind": "action_audit", "action_audit": {**event, "recorded_at": _now()}},
    )


def _value_digest(proposal_id: str, value: str) -> str:
    material = f"{proposal_id}\x00{value.strip()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
