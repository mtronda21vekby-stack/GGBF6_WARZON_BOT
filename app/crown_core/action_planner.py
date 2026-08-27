from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class CrownActionPlanner:
    """Small deterministic semantic planner for high-confidence V1 commands.

    This planner does not execute anything and cannot register new actions. It
    exists so natural-language action requests can enter the same closed
    crown-actions-v1 validation/policy pipeline even before provider-native tool
    calling is enabled. Ambiguous requests deliberately produce no proposal.
    """

    def propose(
        self,
        *,
        text: str,
        source_turn_id: UUID,
        analysis_report_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        normalized = " ".join(str(text or "").strip().split())
        if not normalized:
            return None

        proposal = (
            self._reminder(normalized, source_turn_id)
            or self._memory_save(normalized, source_turn_id)
            or self._memory_forget(normalized, source_turn_id)
            or self._open_analysis(normalized, source_turn_id, analysis_report_id)
            or self._navigate(normalized, source_turn_id)
        )
        if proposal is None:
            return None
        return {"action_proposals": [proposal]}

    def _proposal(
        self,
        *,
        action_id: str,
        arguments: dict[str, Any],
        source_turn_id: UUID,
        rationale: str,
    ) -> dict[str, Any]:
        return {
            "proposal_id": str(uuid4()),
            "action_id": action_id,
            "arguments": arguments,
            "rationale": rationale[:500],
            "source_turn_id": str(source_turn_id),
            "correlation_id": str(uuid4()),
        }

    def _reminder(self, text: str, source_turn_id: UUID) -> dict[str, Any] | None:
        lower = text.lower()
        if not any(marker in lower for marker in ("напомни", "напоминание", "remind me", "reminder")):
            return None

        # V1 only executes unambiguous relative numeric schedules. Calendar
        # expressions such as "tomorrow evening" remain clarification-only
        # until the device-local timezone/date resolver is in the loop.
        patterns = (
            (r"(?:через|in)\s+(\d{1,4})\s*(?:минут(?:у|ы)?|мин\.?|minutes?|mins?)\b", 60),
            (r"(?:через|in)\s+(\d{1,3})\s*(?:час(?:а|ов)?|ч\.?|hours?|hrs?)\b", 3600),
            (r"(?:через|in)\s+(\d{1,2})\s*(?:дн(?:я|ей)?|days?)\b", 86400),
        )
        seconds: int | None = None
        matched: re.Match[str] | None = None
        for pattern, multiplier in patterns:
            candidate = re.search(pattern, lower, flags=re.IGNORECASE)
            if candidate is not None:
                value = int(candidate.group(1))
                calculated = value * multiplier
                if 0 < calculated <= 31_536_000:
                    seconds = calculated
                    matched = candidate
                    break
        if seconds is None or matched is None:
            return None

        title = text
        title = re.sub(r"^\s*(?:напомни(?:\s+мне)?|создай\s+напоминание|remind\s+me|create\s+(?:a\s+)?reminder)\s*", "", title, flags=re.IGNORECASE)
        relative_phrase = text[matched.start():matched.end()]
        title = title.replace(relative_phrase, " ")
        title = re.sub(r"\s+", " ", title).strip(" ,.:;—-")
        if not title:
            title = "BLACK CROWN reminder"
        if len(title) > 160:
            title = title[:160].rstrip()

        return self._proposal(
            action_id="reminder.create",
            arguments={
                "title": title,
                "schedule": {"kind": "relative", "seconds": seconds},
            },
            source_turn_id=source_turn_id,
            rationale="User explicitly requested a reminder with an unambiguous relative schedule.",
        )

    def _memory_save(self, text: str, source_turn_id: UUID) -> dict[str, Any] | None:
        lower = text.lower()
        if not any(marker in lower for marker in ("запомни", "remember")):
            return None

        fields = (
            ("current_goal", ("цель", "goal")),
            ("training_focus", ("фокус тренировки", "training focus")),
            ("weekly_focus", ("фокус недели", "weekly focus")),
            ("playstyle", ("стиль игры", "playstyle", "play style")),
        )
        field: str | None = None
        marker_used: str | None = None
        for candidate, markers in fields:
            for marker in markers:
                if marker in lower:
                    field = candidate
                    marker_used = marker
                    break
            if field is not None:
                break
        if field is None or marker_used is None:
            return None

        value = text
        colon = value.find(":")
        if colon >= 0:
            value = value[colon + 1 :]
        else:
            index = lower.find(marker_used)
            value = value[index + len(marker_used) :]
        value = value.strip(" ,.:;—-")
        if not value or len(value) > 500:
            return None

        return self._proposal(
            action_id="memory.propose_save",
            arguments={"field": field, "value": value},
            source_turn_id=source_turn_id,
            rationale="User explicitly asked BLACK CROWN to remember an allow-listed profile field.",
        )

    def _memory_forget(self, text: str, source_turn_id: UUID) -> dict[str, Any] | None:
        lower = text.lower()
        if not any(marker in lower for marker in ("забудь", "удали из памяти", "forget", "remove from memory")):
            return None
        fields = (
            ("current_goal", ("цель", "goal")),
            ("training_focus", ("фокус тренировки", "training focus")),
            ("weekly_focus", ("фокус недели", "weekly focus")),
            ("playstyle", ("стиль игры", "playstyle", "play style")),
        )
        for field, markers in fields:
            if any(marker in lower for marker in markers):
                return self._proposal(
                    action_id="memory.forget",
                    arguments={"field": field},
                    source_turn_id=source_turn_id,
                    rationale="User explicitly requested removal of a resolved allow-listed memory field.",
                )
        return None

    def _open_analysis(
        self,
        text: str,
        source_turn_id: UUID,
        analysis_report_id: UUID | None,
    ) -> dict[str, Any] | None:
        if analysis_report_id is None:
            return None
        lower = text.lower()
        if not any(marker in lower for marker in ("открой анализ", "открой отчёт", "open analysis", "open report")):
            return None
        return self._proposal(
            action_id="analyze.open_report",
            arguments={"report_id": str(analysis_report_id)},
            source_turn_id=source_turn_id,
            rationale="User explicitly requested the owner-scoped analysis report already attached to this turn.",
        )

    def _navigate(self, text: str, source_turn_id: UUID) -> dict[str, Any] | None:
        lower = text.lower()
        if not any(marker in lower for marker in ("открой", "перейди", "покажи", "open", "go to", "show")):
            return None
        destinations = (
            ("war_room", ("штаб", "war room")),
            ("analyze", ("анализ", "analyze")),
            ("brain", ("brain", "мозг", "профиль")),
            ("history", ("история", "history")),
            ("settings", ("настройки", "settings")),
            ("live", ("live", "лайв")),
        )
        for destination, markers in destinations:
            if any(marker in lower for marker in markers):
                return self._proposal(
                    action_id="app.navigate",
                    arguments={"destination": destination},
                    source_turn_id=source_turn_id,
                    rationale="User explicitly requested navigation to a known BLACK CROWN surface.",
                )
        return None
