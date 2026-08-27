from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


ACTION_PROTOCOL_VERSION = "crown-actions-v1"


class ActionRisk(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    SENSITIVE_WRITE = "sensitive_write"
    PROHIBITED = "prohibited"


class ConfirmationPolicy(str, Enum):
    NEVER = "never"
    REQUIRED = "required"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    risk: ActionRisk
    confirmation: ConfirmationPolicy
    requires_authentication: bool
    device_only: bool = False


@dataclass(frozen=True)
class CrownActionProposal:
    proposal_id: UUID
    action_id: str
    arguments: dict[str, Any]
    rationale: str
    source_turn_id: UUID
    correlation_id: UUID

    def projection(self) -> dict[str, Any]:
        return {
            "protocol_version": ACTION_PROTOCOL_VERSION,
            "proposal_id": str(self.proposal_id),
            "action_id": self.action_id,
            "arguments": dict(self.arguments),
            "rationale": self.rationale,
            "source_turn_id": str(self.source_turn_id),
            "correlation_id": str(self.correlation_id),
        }


class ActionValidationFailure(ValueError):
    """Stable fail-closed code for malformed provider action proposals."""

    def __init__(self, code: str) -> None:
        normalized = str(code or "invalid_action_proposal").strip()[:80]
        super().__init__(normalized)
        self.code = normalized


class CrownActionRegistry:
    """Server-owned allow-list. Provider output can never register executable actions."""

    _definitions = {
        "app.navigate": ActionDefinition(
            "app.navigate", ActionRisk.READ_ONLY, ConfirmationPolicy.NEVER, False, True
        ),
        "memory.propose_save": ActionDefinition(
            "memory.propose_save", ActionRisk.REVERSIBLE_WRITE, ConfirmationPolicy.REQUIRED, True
        ),
        "memory.forget": ActionDefinition(
            "memory.forget", ActionRisk.SENSITIVE_WRITE, ConfirmationPolicy.DESTRUCTIVE, True
        ),
        "reminder.create": ActionDefinition(
            "reminder.create", ActionRisk.REVERSIBLE_WRITE, ConfirmationPolicy.REQUIRED, False, True
        ),
        "analyze.open_report": ActionDefinition(
            "analyze.open_report", ActionRisk.READ_ONLY, ConfirmationPolicy.NEVER, True, True
        ),
    }

    @classmethod
    def definition(cls, action_id: str) -> ActionDefinition:
        try:
            return cls._definitions[str(action_id)]
        except KeyError:
            raise ActionValidationFailure("unknown_action") from None

    @classmethod
    def capabilities(cls) -> tuple[str, ...]:
        return tuple(cls._definitions)


_ALLOWED_MEMORY_FIELDS = {"current_goal", "training_focus", "weekly_focus", "playstyle"}
_ALLOWED_DESTINATIONS = {"live", "war_room", "analyze", "brain", "history", "settings"}


def normalize_action_proposal(raw: dict[str, Any], *, source_turn_id: UUID) -> CrownActionProposal:
    """Validate untrusted provider/tool output into a bounded CROWN-native proposal."""
    if not isinstance(raw, dict):
        raise ActionValidationFailure("invalid_action_proposal")
    action_id = str(raw.get("action_id") or "").strip()
    CrownActionRegistry.definition(action_id)
    try:
        proposal_id = UUID(str(raw.get("proposal_id") or ""))
        correlation_id = UUID(str(raw.get("correlation_id") or ""))
    except ValueError:
        raise ActionValidationFailure("invalid_action_identifier") from None
    rationale = str(raw.get("rationale") or "").strip()[:500]
    arguments = _validate_arguments(action_id, raw.get("arguments"))
    return CrownActionProposal(
        proposal_id=proposal_id,
        action_id=action_id,
        arguments=arguments,
        rationale=rationale,
        source_turn_id=source_turn_id,
        correlation_id=correlation_id,
    )


def _validate_arguments(action_id: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ActionValidationFailure("invalid_action_arguments")

    if action_id == "app.navigate":
        destination = str(value.get("destination") or "").strip()
        if destination not in _ALLOWED_DESTINATIONS:
            raise ActionValidationFailure("invalid_destination")
        return {"destination": destination}

    if action_id == "memory.propose_save":
        field = str(value.get("field") or "").strip()
        text = str(value.get("value") or "").strip()
        if field not in _ALLOWED_MEMORY_FIELDS or not text or len(text) > 240:
            raise ActionValidationFailure("invalid_memory_proposal")
        return {"field": field, "value": text}

    if action_id == "memory.forget":
        field = str(value.get("field") or "").strip()
        if field not in _ALLOWED_MEMORY_FIELDS:
            raise ActionValidationFailure("invalid_memory_target")
        return {"field": field}

    if action_id == "reminder.create":
        title = str(value.get("title") or "").strip()
        note = str(value.get("note") or "").strip()
        schedule = value.get("schedule")
        if not title or len(title) > 160 or len(note) > 500 or not isinstance(schedule, dict):
            raise ActionValidationFailure("invalid_reminder")
        kind = str(schedule.get("kind") or "").strip()
        if kind == "absolute":
            iso8601 = str(schedule.get("iso8601") or "").strip()
            if not iso8601 or len(iso8601) > 64:
                raise ActionValidationFailure("invalid_reminder_schedule")
            normalized_schedule = {"kind": "absolute", "iso8601": iso8601}
        elif kind == "relative":
            try:
                seconds = int(schedule.get("seconds"))
            except (TypeError, ValueError):
                raise ActionValidationFailure("invalid_reminder_schedule") from None
            if seconds <= 0 or seconds > 31_536_000:
                raise ActionValidationFailure("invalid_reminder_schedule")
            normalized_schedule = {"kind": "relative", "seconds": seconds}
        elif kind == "local":
            try:
                days_from_today = int(schedule.get("days_from_today"))
                hour = int(schedule.get("hour"))
                minute = int(schedule.get("minute", 0))
            except (TypeError, ValueError):
                raise ActionValidationFailure("invalid_reminder_schedule") from None
            if not 0 <= days_from_today <= 365 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ActionValidationFailure("invalid_reminder_schedule")
            normalized_schedule = {
                "kind": "local",
                "days_from_today": days_from_today,
                "hour": hour,
                "minute": minute,
            }
        else:
            raise ActionValidationFailure("invalid_reminder_schedule")
        result: dict[str, Any] = {"title": title, "schedule": normalized_schedule}
        if note:
            result["note"] = note
        return result

    if action_id == "analyze.open_report":
        try:
            report_id = UUID(str(value.get("report_id") or ""))
        except ValueError:
            raise ActionValidationFailure("invalid_report_id") from None
        return {"report_id": str(report_id)}

    raise ActionValidationFailure("unknown_action")
