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

        relative = self._relative_reminder_schedule(lower)
        if relative is not None:
            schedule, matched = relative
            title = self._reminder_title(text, matched.group(0))
            return self._proposal(
                action_id="reminder.create",
                arguments={"title": title, "schedule": schedule},
                source_turn_id=source_turn_id,
                rationale="User explicitly requested a reminder with an unambiguous relative schedule.",
            )

        local = self._local_reminder_schedule(lower)
        if local is not None:
            schedule, matched_phrase = local
            title = self._reminder_title(text, matched_phrase)
            return self._proposal(
                action_id="reminder.create",
                arguments={"title": title, "schedule": schedule},
                source_turn_id=source_turn_id,
                rationale=(
                    "User explicitly requested a reminder with an unambiguous local calendar day and clock time. "
                    "The device resolves the final date in its current calendar and timezone."
                ),
            )

        # Expressions without both a resolvable day and clock time remain
        # clarification-only. The model is never allowed to guess the user's
        # local timezone or silently choose an hour.
        return None

    @staticmethod
    def _relative_reminder_schedule(lower: str) -> tuple[dict[str, Any], re.Match[str]] | None:
        patterns = (
            (r"(?:через|in)\s+(\d{1,4})\s*(?:минут(?:у|ы)?|мин\.?|minutes?|mins?)\b", 60),
            (r"(?:через|in)\s+(\d{1,3})\s*(?:час(?:а|ов)?|ч\.?|hours?|hrs?)\b", 3600),
            (r"(?:через|in)\s+(\d{1,2})\s*(?:дн(?:я|ей)?|days?)\b", 86400),
        )
        for pattern, multiplier in patterns:
            candidate = re.search(pattern, lower, flags=re.IGNORECASE)
            if candidate is None:
                continue
            calculated = int(candidate.group(1)) * multiplier
            if 0 < calculated <= 31_536_000:
                return {"kind": "relative", "seconds": calculated}, candidate
        return None

    @staticmethod
    def _local_reminder_schedule(lower: str) -> tuple[dict[str, Any], str] | None:
        day_patterns = (
            (r"\b(?:завтра|tomorrow)\b", 1),
            (r"\b(?:сегодня|today)\b", 0),
        )
        day_match: re.Match[str] | None = None
        days_from_today: int | None = None
        for pattern, offset in day_patterns:
            candidate = re.search(pattern, lower, flags=re.IGNORECASE)
            if candidate is not None:
                day_match = candidate
                days_from_today = offset
                break
        if day_match is None or days_from_today is None:
            return None

        # Require an explicit clock marker. Accept "в 20", "в 20:30",
        # "at 8 pm" and "at 20:00". Bare numbers are intentionally ignored.
        clock = re.search(
            r"(?:\bв\s+|\bat\s+)(\d{1,2})(?::([0-5]\d))?\s*(am|pm)?\b",
            lower,
            flags=re.IGNORECASE,
        )
        if clock is None:
            return None
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
        meridiem = str(clock.group(3) or "").lower()
        if meridiem:
            if not 1 <= hour <= 12:
                return None
            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
        elif not 0 <= hour <= 23:
            return None

        start = min(day_match.start(), clock.start())
        end = max(day_match.end(), clock.end())
        matched_phrase = lower[start:end]
        return (
            {
                "kind": "local",
                "days_from_today": days_from_today,
                "hour": hour,
                "minute": minute,
            },
            matched_phrase,
        )

    @staticmethod
    def _reminder_title(text: str, schedule_phrase: str) -> str:
        title = re.sub(
            r"^\s*(?:напомни(?:\s+мне)?|создай\s+напоминание|remind\s+me|create\s+(?:a\s+)?reminder)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        if schedule_phrase:
            title = re.sub(re.escape(schedule_phrase), " ", title, count=1, flags=re.IGNORECASE)
        title = re.sub(r"\s+", " ", title).strip(" ,.:;—-")
        if not title:
            title = "BLACK CROWN reminder"
        return title[:160].rstrip()

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
