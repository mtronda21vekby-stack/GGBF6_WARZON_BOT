# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class QualityTelemetry:
    """Process-local quality counters with no conversation content.

    This is deliberately lightweight. It measures reliability/latency/feedback
    without logging prompts, Telegram initData, user text, tokens or secrets.
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

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = self._total
            rated = self._feedback_helpful + self._feedback_not_helpful
            return {
                "requests": total,
                "avg_latency_ms": round(self._latency_ms / total, 1) if total else 0.0,
                "retry_attempts": self._retry_attempts,
                "anti_repeat_retries": self._anti_repeat_retries,
                "currentness_blocked": self._currentness_blocked,
                "errors": self._errors,
                "empty_outputs": self._empty_outputs,
                "feedback": {
                    "rated": rated,
                    "helpful": self._feedback_helpful,
                    "not_helpful": self._feedback_not_helpful,
                    "helpful_rate": round(self._feedback_helpful / rated, 3) if rated else None,
                },
                "intents": dict(self._intents.most_common(12)),
                "knowledge": dict(self._knowledge.most_common(8)),
                "outcomes": dict(self._outcomes.most_common(8)),
            }


quality_telemetry = QualityTelemetry()
