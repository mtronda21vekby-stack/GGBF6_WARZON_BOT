# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable


_CANONICAL_PROMOTION_BLOCKERS = {
    "shadow_disabled",
    "dual_write_disabled",
    "identity_conflict",
    "merge_pending",
    "coverage_incomplete",
    "schema_mismatch",
    "control_error",
}


@dataclass
class QualityTelemetry:
    """Process-local quality counters with no conversation content.

    This is deliberately lightweight. It measures reliability, latency,
    feedback and canonical-read migration parity without logging prompts,
    Telegram initData, user text, canonical IDs, tokens or secrets.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _total: int = 0
    _latency_ms: int = 0
    _retry_attempts: int = 0
    _anti_repeat_retries: int = 0
    _currentness_blocked: int = 0
    _errors: int = 0
    _empty_outputs: int = 0
    _feedback_helpful: int = 0
    _feedback_not_helpful: int = 0
    _intents: Counter = field(default_factory=Counter, repr=False)
    _knowledge: Counter = field(default_factory=Counter, repr=False)
    _outcomes: Counter = field(default_factory=Counter, repr=False)

    _canonical_read_shadow_enabled: bool = False
    _canonical_read_shadow_sample_rate: float = 0.0
    _canonical_read_database_enabled: bool | None = None
    _canonical_read_control_reason: str = ""
    _canonical_read_control_checked_at: str = ""
    _canonical_read_control_errors: int = 0
    _canonical_read_promotion_ready: bool = False
    _canonical_read_coverage_ready: bool = False
    _canonical_read_promotion_blockers: tuple[str, ...] = ()
    _canonical_read_conflict_count: int = 0
    _canonical_read_merge_pending_count: int = 0
    _canonical_read_events: int = 0
    _canonical_read_comparisons: int = 0
    _canonical_read_latency_ms: int = 0
    _canonical_read_legacy_items: int = 0
    _canonical_read_canonical_items: int = 0
    _canonical_read_surfaces: Counter = field(default_factory=Counter, repr=False)
    _canonical_read_outcomes: Counter = field(default_factory=Counter, repr=False)

    def record_reply(
        self,
        *,
        intent: str,
        latency_ms: int,
        knowledge: str,
        outcome: str = "ok",
        attempts: int = 1,
        anti_repeat_retry: bool = False,
        currentness_blocked: bool = False,
    ) -> None:
        with self._lock:
            self._total += 1
            self._latency_ms += max(0, int(latency_ms or 0))
            self._retry_attempts += max(0, int(attempts or 1) - 1)
            self._anti_repeat_retries += int(bool(anti_repeat_retry))
            self._currentness_blocked += int(bool(currentness_blocked))
            if outcome == "error":
                self._errors += 1
            if outcome == "empty":
                self._empty_outputs += 1
            self._intents[str(intent or "UNKNOWN")[:64]] += 1
            self._knowledge[str(knowledge or "UNKNOWN")[:64]] += 1
            self._outcomes[str(outcome or "unknown")[:32]] += 1

    def record_feedback(self, rating: str) -> None:
        with self._lock:
            if rating == "helpful":
                self._feedback_helpful += 1
            elif rating == "not_helpful":
                self._feedback_not_helpful += 1

    def configure_canonical_read_shadow(
        self,
        *,
        enabled: bool,
        sample_rate: float,
    ) -> None:
        with self._lock:
            self._canonical_read_shadow_enabled = bool(enabled)
            self._canonical_read_shadow_sample_rate = max(
                0.0,
                min(1.0, float(sample_rate or 0.0)),
            )

    @staticmethod
    def _sanitize_promotion_blockers(
        blockers: Iterable[Any] | None,
    ) -> tuple[str, ...]:
        safe = {
            str(item or "").strip().casefold()
            for item in (blockers or ())
        }
        return tuple(sorted(safe & _CANONICAL_PROMOTION_BLOCKERS))

    def configure_canonical_read_control(
        self,
        *,
        database_enabled: bool | None,
        reason: str = "",
        checked_at: str = "",
        error: str = "",
        promotion_ready: bool = False,
        coverage_ready: bool = False,
        promotion_blockers: Iterable[Any] | None = None,
        conflict_count: int = 0,
        merge_pending_count: int = 0,
    ) -> None:
        """Record only sanitized operational control state.

        Raw identity values, provider subjects, database operator notes and
        player payloads are never accepted by this boundary. `reason` is a
        stable application state code, not the free-form database flag reason.
        """

        with self._lock:
            self._canonical_read_database_enabled = (
                database_enabled
                if isinstance(database_enabled, bool)
                else None
            )
            self._canonical_read_control_reason = str(reason or "")[:128]
            self._canonical_read_control_checked_at = str(checked_at or "")[:64]
            self._canonical_read_promotion_ready = bool(promotion_ready)
            self._canonical_read_coverage_ready = bool(coverage_ready)
            self._canonical_read_promotion_blockers = (
                self._sanitize_promotion_blockers(promotion_blockers)
            )
            self._canonical_read_conflict_count = max(
                0,
                int(conflict_count or 0),
            )
            self._canonical_read_merge_pending_count = max(
                0,
                int(merge_pending_count or 0),
            )
            if error:
                self._canonical_read_control_errors += 1

    def record_canonical_read(
        self,
        *,
        surface: str,
        outcome: str,
        latency_ms: int,
        legacy_items: int,
        canonical_items: int,
        compared: bool,
    ) -> None:
        """Record only migration-control metadata, never identity or content."""

        with self._lock:
            self._canonical_read_events += 1
            self._canonical_read_comparisons += int(bool(compared))
            self._canonical_read_latency_ms += max(0, int(latency_ms or 0))
            self._canonical_read_legacy_items += max(0, int(legacy_items or 0))
            self._canonical_read_canonical_items += max(
                0,
                int(canonical_items or 0),
            )
            self._canonical_read_surfaces[
                str(surface or "unknown")[:64]
            ] += 1
            self._canonical_read_outcomes[
                str(outcome or "unknown")[:64]
            ] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = self._total
            rated = self._feedback_helpful + self._feedback_not_helpful
            canonical_events = self._canonical_read_events
            canonical_comparisons = self._canonical_read_comparisons
            return {
                "requests": total,
                "avg_latency_ms": (
                    round(self._latency_ms / total, 1) if total else 0.0
                ),
                "retry_attempts": self._retry_attempts,
                "anti_repeat_retries": self._anti_repeat_retries,
                "currentness_blocked": self._currentness_blocked,
                "errors": self._errors,
                "empty_outputs": self._empty_outputs,
                "feedback": {
                    "rated": rated,
                    "helpful": self._feedback_helpful,
                    "not_helpful": self._feedback_not_helpful,
                    "helpful_rate": (
                        round(self._feedback_helpful / rated, 3)
                        if rated
                        else None
                    ),
                },
                "intents": dict(self._intents.most_common(12)),
                "knowledge": dict(self._knowledge.most_common(8)),
                "outcomes": dict(self._outcomes.most_common(8)),
                "canonical_read_shadow": {
                    "enabled": self._canonical_read_shadow_enabled,
                    "sample_rate": self._canonical_read_shadow_sample_rate,
                    "database_enabled": self._canonical_read_database_enabled,
                    "control_reason": self._canonical_read_control_reason,
                    "control_checked_at": (
                        self._canonical_read_control_checked_at or None
                    ),
                    "control_errors": self._canonical_read_control_errors,
                    "promotion_ready": self._canonical_read_promotion_ready,
                    "promotion_blockers": list(
                        self._canonical_read_promotion_blockers
                    ),
                    "coverage_ready": self._canonical_read_coverage_ready,
                    "identity_conflicts": self._canonical_read_conflict_count,
                    "merge_pending": (
                        self._canonical_read_merge_pending_count
                    ),
                    "read_authority": "legacy",
                    "returns_legacy": True,
                    "canonical_returned_to_callers": False,
                    "canonical_primary_enabled": False,
                    "events": canonical_events,
                    "comparisons": canonical_comparisons,
                    "comparison_rate": (
                        round(canonical_comparisons / canonical_events, 3)
                        if canonical_events
                        else None
                    ),
                    "avg_shadow_latency_ms": (
                        round(
                            self._canonical_read_latency_ms
                            / canonical_events,
                            1,
                        )
                        if canonical_events
                        else 0.0
                    ),
                    "legacy_items_observed": self._canonical_read_legacy_items,
                    "canonical_items_observed": (
                        self._canonical_read_canonical_items
                    ),
                    "surfaces": dict(
                        self._canonical_read_surfaces.most_common(12)
                    ),
                    "outcomes": dict(
                        self._canonical_read_outcomes.most_common(12)
                    ),
                },
            }


quality_telemetry = QualityTelemetry()
