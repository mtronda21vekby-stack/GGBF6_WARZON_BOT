# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import threading
import time
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Iterable


@dataclass(frozen=True)
class WindowLimit:
    max_events: int
    window_s: float

    def normalized(self) -> "WindowLimit":
        return WindowLimit(max(1, int(self.max_events)), max(1.0, float(self.window_s)))


@dataclass(frozen=True)
class UsageDecision:
    allowed: bool
    category: str
    retry_after_s: int = 0
    scope: str = "subject"


@dataclass(frozen=True)
class GuardRule:
    subject_limits: tuple[WindowLimit, ...] = ()
    global_limits: tuple[WindowLimit, ...] = ()


class UsageGuard:
    """Process-local abuse/cost guard for expensive server capabilities.

    STT and TTS have independent budgets so a normal duplex exchange does not
    count twice against one opaque voice bucket. The guard intentionally does
    not identify users in telemetry and remains bounded against forged IDs.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        rules: dict[str, GuardRule] | None = None,
        clock: Callable[[], float] = time.monotonic,
        max_buckets: int = 10_000,
    ) -> None:
        self.enabled = bool(enabled)
        self._clock = clock
        self._max_buckets = max(128, int(max_buckets or 10_000))
        self._rules = {
            str(category): GuardRule(
                subject_limits=tuple(x.normalized() for x in rule.subject_limits),
                global_limits=tuple(x.normalized() for x in rule.global_limits),
            )
            for category, rule in dict(rules or {}).items()
        }
        self._buckets: "OrderedDict[tuple[str, str], Deque[float]]" = OrderedDict()
        self._allowed: Counter[str] = Counter()
        self._blocked: Counter[str] = Counter()
        self._lock = threading.RLock()

    @classmethod
    def from_settings(cls, settings: Any) -> "UsageGuard":
        def _limit(name: str, default: int, window_s: int) -> WindowLimit | None:
            raw = getattr(settings, name, default)
            try:
                value = int(raw)
            except Exception:
                value = default
            if value <= 0:
                return None
            return WindowLimit(value, float(window_s))

        def _limits(items: Iterable[WindowLimit | None]) -> tuple[WindowLimit, ...]:
            return tuple(x for x in items if x is not None)

        rules = {
            "ai": GuardRule(
                subject_limits=_limits((
                    _limit("ai_rate_limit_1m", 12, 60),
                    _limit("ai_rate_limit_1h", 120, 3600),
                )),
                global_limits=_limits((
                    _limit("ai_global_rate_limit_1m", 180, 60),
                    _limit("ai_global_rate_limit_1h", 1800, 3600),
                )),
            ),
            "vod": GuardRule(
                subject_limits=_limits((
                    _limit("vod_rate_limit_10m", 3, 600),
                    _limit("vod_rate_limit_1h", 12, 3600),
                )),
                global_limits=_limits((
                    _limit("vod_global_rate_limit_10m", 30, 600),
                    _limit("vod_global_rate_limit_1h", 120, 3600),
                )),
            ),
            "stt": GuardRule(
                subject_limits=_limits((
                    _limit("stt_rate_limit_1m", 12, 60),
                    _limit("stt_rate_limit_1h", 90, 3600),
                )),
                global_limits=_limits((
                    _limit("stt_global_rate_limit_1m", 150, 60),
                    _limit("stt_global_rate_limit_1h", 1200, 3600),
                )),
            ),
            "voice": GuardRule(
                subject_limits=_limits((
                    _limit("voice_rate_limit_1m", 10, 60),
                    _limit("voice_rate_limit_1h", 60, 3600),
                )),
                global_limits=_limits((
                    _limit("voice_global_rate_limit_1m", 120, 60),
                    _limit("voice_global_rate_limit_1h", 1200, 3600),
                )),
            ),
            "skill": GuardRule(
                subject_limits=_limits((
                    _limit("skill_rate_limit_1m", 30, 60),
                    _limit("skill_rate_limit_1h", 300, 3600),
                )),
                global_limits=_limits((
                    _limit("skill_global_rate_limit_1m", 600, 60),
                    _limit("skill_global_rate_limit_1h", 6000, 3600),
                )),
            ),
        }
        return cls(
            enabled=bool(getattr(settings, "usage_guard_enabled", True)),
            rules=rules,
            max_buckets=int(getattr(settings, "usage_guard_max_buckets", 10_000) or 10_000),
        )

    @staticmethod
    def _subject_key(subject: Any) -> str:
        try:
            return str(int(subject))
        except Exception:
            text = str(subject or "unknown").strip()
            return text[:96] or "unknown"

    @staticmethod
    def _retry_after(events: Deque[float], now: float, limit: WindowLimit) -> float:
        threshold = now - limit.window_s
        relevant = [ts for ts in events if ts > threshold]
        if len(relevant) < limit.max_events:
            return 0.0
        index = len(relevant) - limit.max_events
        unblock_at = relevant[index] + limit.window_s
        return max(0.0, unblock_at - now)

    @staticmethod
    def _prune(events: Deque[float], now: float, max_window_s: float) -> None:
        threshold = now - max_window_s
        while events and events[0] <= threshold:
            events.popleft()

    def _bucket(self, key: tuple[str, str]) -> Deque[float]:
        bucket = self._buckets.get(key)
        if bucket is None:
            while len(self._buckets) >= self._max_buckets:
                victim = next(
                    (
                        existing
                        for existing in self._buckets.keys()
                        if existing[1] != "global" and existing != key
                    ),
                    None,
                )
                if victim is None:
                    break
                del self._buckets[victim]
            bucket = deque()
            self._buckets[key] = bucket
        else:
            self._buckets.move_to_end(key)
        return bucket

    def check(self, subject: Any, category: str) -> UsageDecision:
        category = str(category or "").strip().lower()
        if not self.enabled:
            return UsageDecision(True, category or "unknown")
        rule = self._rules.get(category)
        if rule is None or (not rule.subject_limits and not rule.global_limits):
            return UsageDecision(True, category or "unknown")

        subject_key = self._subject_key(subject)
        now = float(self._clock())
        subject_bucket_key = (category, f"subject:{subject_key}")
        global_bucket_key = (category, "global")

        with self._lock:
            subject_events = self._bucket(subject_bucket_key)
            global_events = self._bucket(global_bucket_key)

            max_subject_window = max((x.window_s for x in rule.subject_limits), default=1.0)
            max_global_window = max((x.window_s for x in rule.global_limits), default=1.0)
            self._prune(subject_events, now, max_subject_window)
            self._prune(global_events, now, max_global_window)

            waits: list[tuple[str, float]] = []
            for limit in rule.subject_limits:
                wait = self._retry_after(subject_events, now, limit)
                if wait > 0:
                    waits.append(("subject", wait))
            for limit in rule.global_limits:
                wait = self._retry_after(global_events, now, limit)
                if wait > 0:
                    waits.append(("global", wait))

            if waits:
                scope, wait = max(waits, key=lambda item: item[1])
                self._blocked[category] += 1
                return UsageDecision(False, category, retry_after_s=max(1, int(math.ceil(wait))), scope=scope)

            subject_events.append(now)
            global_events.append(now)
            self._allowed[category] += 1
            return UsageDecision(True, category)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "active_buckets": len(self._buckets),
                "allowed": dict(self._allowed),
                "blocked": dict(self._blocked),
                "categories": {
                    category: {
                        "subject": [{"max": x.max_events, "window_s": int(x.window_s)} for x in rule.subject_limits],
                        "global": [{"max": x.max_events, "window_s": int(x.window_s)} for x in rule.global_limits],
                    }
                    for category, rule in self._rules.items()
                },
            }


class UpdateReplayGuard:
    """Bounded TTL dedupe for Telegram update_id values."""

    def __init__(
        self,
        *,
        ttl_s: float = 15 * 60,
        max_entries: int = 20_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_s = max(30.0, float(ttl_s or 900.0))
        self.max_entries = max(128, int(max_entries or 20_000))
        self._clock = clock
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.RLock()
        self.duplicates = 0

    def _prune(self, now: float) -> None:
        threshold = now - self.ttl_s
        while self._seen:
            first_key = next(iter(self._seen))
            if self._seen[first_key] > threshold:
                break
            self._seen.popitem(last=False)

    def accept(self, update_id: Any) -> bool:
        key = str(update_id)
        now = float(self._clock())
        with self._lock:
            self._prune(now)
            existing = self._seen.get(key)
            if existing is not None and existing > now - self.ttl_s:
                self.duplicates += 1
                self._seen.move_to_end(key)
                return False
            self._seen[key] = now
            self._seen.move_to_end(key)
            while len(self._seen) > self.max_entries:
                self._seen.popitem(last=False)
            return True

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {"tracked": len(self._seen), "duplicates": int(self.duplicates)}
