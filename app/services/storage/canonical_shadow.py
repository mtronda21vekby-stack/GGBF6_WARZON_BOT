# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import time
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from app.observability.quality import QualityTelemetry, quality_telemetry


@dataclass(frozen=True)
class CanonicalReadResult:
    value: Any
    row_count: int
    ambiguous: bool = False


class CanonicalReadShadowStore:
    """Read-only canonical parity probe around the persistent Supabase adapter.

    The wrapper never changes the value returned to product code. Legacy reads
    remain authoritative while sampled canonical reads are compared and emitted
    as content-free telemetry. Shadow failures are isolated from the live read.
    """

    def __init__(
        self,
        primary: Any,
        *,
        enabled: bool = True,
        sample_rate: float = 1.0,
        identity_cache_ttl_s: float = 120.0,
        identity_negative_cache_ttl_s: float = 5.0,
        identity_cache_max_entries: int = 10_000,
        telemetry: QualityTelemetry | None = None,
    ) -> None:
        self.primary = primary
        self.enabled = bool(enabled)
        self.sample_rate = max(0.0, min(1.0, float(sample_rate or 0.0)))
        self.identity_cache_ttl_s = max(1.0, float(identity_cache_ttl_s or 120.0))
        self.identity_negative_cache_ttl_s = max(
            0.5,
            min(
                self.identity_cache_ttl_s,
                float(identity_negative_cache_ttl_s or 5.0),
            ),
        )
        self.identity_cache_max_entries = max(
            32,
            min(int(identity_cache_max_entries or 10_000), 100_000),
        )
        self.telemetry = telemetry or quality_telemetry
        self._identity_cache: OrderedDict[int, tuple[float, tuple[str, ...]]] = OrderedDict()
        self._identity_cache_lock = threading.RLock()
        self.telemetry.configure_canonical_read_shadow(
            enabled=self.enabled,
            sample_rate=self.sample_rate,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.primary, name)

    def close(self) -> None:
        close = getattr(self.primary, "close", None)
        if callable(close):
            close()

    def canonical_read_shadow_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sample_rate": self.sample_rate,
            "identity_cache_entries": self._identity_cache_size(),
            "identity_cache_max_entries": self.identity_cache_max_entries,
            "returns_legacy": True,
            "canonical_primary_enabled": False,
        }

    def _identity_cache_size(self) -> int:
        with self._identity_cache_lock:
            return len(self._identity_cache)

    @staticmethod
    def _cardinality(value: Any) -> int:
        if isinstance(value, (list, tuple, set, dict)):
            return len(value)
        return int(value not in (None, ""))

    @staticmethod
    def _is_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (str, bytes, list, tuple, set, dict)):
            return len(value) == 0
        return False

    @staticmethod
    def _is_subsequence(needle: list[Any], haystack: list[Any]) -> bool:
        if not needle:
            return True
        position = 0
        for item in haystack:
            if item == needle[position]:
                position += 1
                if position == len(needle):
                    return True
        return False

    @classmethod
    def _classify(cls, legacy: Any, canonical: Any) -> str:
        if legacy == canonical:
            return "match"
        legacy_empty = cls._is_empty(legacy)
        canonical_empty = cls._is_empty(canonical)
        if legacy_empty and not canonical_empty:
            return "canonical_only"
        if canonical_empty and not legacy_empty:
            return "canonical_empty"
        if isinstance(legacy, list) and isinstance(canonical, list):
            if cls._is_subsequence(legacy, canonical):
                return "canonical_superset"
            if cls._is_subsequence(canonical, legacy):
                return "canonical_subset"
        return "mismatch"

    def _sampled(self, chat_id: int, surface: str) -> bool:
        if not self.enabled or self.sample_rate <= 0.0:
            return False
        if self.sample_rate >= 1.0:
            return True
        digest = hashlib.blake2s(
            f"{int(chat_id)}:{surface}".encode("utf-8"),
            digest_size=4,
        ).digest()
        bucket = int.from_bytes(digest, "big") / 2**32
        return bucket < self.sample_rate

    @staticmethod
    def _parse_uuid_candidates(payload: Any) -> tuple[str, ...]:
        raw = payload
        if isinstance(raw, dict) and len(raw) == 1:
            raw = next(iter(raw.values()))
        if isinstance(raw, list) and len(raw) == 1:
            first = raw[0]
            if isinstance(first, dict) and len(first) == 1:
                raw = next(iter(first.values()))
            elif isinstance(first, list):
                raw = first
        if isinstance(raw, str):
            value = raw.strip()
            if value.startswith("{") and value.endswith("}"):
                raw = [part for part in value[1:-1].split(",") if part]
            elif value:
                raw = [value]
            else:
                raw = []
        if not isinstance(raw, list):
            return ()

        candidates: set[str] = set()
        for item in raw:
            try:
                candidates.add(str(uuid.UUID(str(item).strip())))
            except (TypeError, ValueError, AttributeError):
                continue
        return tuple(sorted(candidates))

    def _cache_identity(
        self,
        chat_id: int,
        candidates: tuple[str, ...],
        *,
        now: float,
    ) -> None:
        ttl = (
            self.identity_cache_ttl_s
            if len(candidates) == 1
            else self.identity_negative_cache_ttl_s
        )
        with self._identity_cache_lock:
            self._identity_cache[int(chat_id)] = (now + ttl, candidates)
            self._identity_cache.move_to_end(int(chat_id))
            while len(self._identity_cache) > self.identity_cache_max_entries:
                self._identity_cache.popitem(last=False)

    def _identity_candidates(self, chat_id: int) -> tuple[str, ...]:
        now = time.monotonic()
        with self._identity_cache_lock:
            cached = self._identity_cache.get(int(chat_id))
            if cached is not None:
                expires_at, candidates = cached
                if expires_at > now:
                    self._identity_cache.move_to_end(int(chat_id))
                    return candidates
                self._identity_cache.pop(int(chat_id), None)

        response = self.primary._request(
            "POST",
            "rpc/black_crown_eligible_identity_candidates",
            json={
                "p_provider": "telegram",
                "p_subject": str(int(chat_id)),
            },
        )
        payload = response.json() if response.content else []
        candidates = self._parse_uuid_candidates(payload)
        self._cache_identity(int(chat_id), candidates, now=now)
        return candidates

    def _canonical_rows(
        self,
        table: str,
        owner_id: str,
        *,
        select: str,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {
            "black_crown_user_id": f"eq.{owner_id}",
            "select": select,
        }
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(max(1, int(limit)))
        response = self.primary._request("GET", table, params=params)
        return self.primary._rows(response)

    @staticmethod
    def _stable_value(value: Any) -> str:
        try:
            return json.dumps(
                value,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            return repr(value)

    def _canonical_player_field(
        self,
        owner_id: str,
        field: str,
        *,
        default: Any,
    ) -> CanonicalReadResult:
        rows = self._canonical_rows(
            "bco_players",
            owner_id,
            select=f"{field},updated_at",
            order="updated_at.desc",
            limit=20,
        )
        if not rows:
            return CanonicalReadResult(default, 0)
        values = [row.get(field, default) for row in rows]
        ambiguous = len({self._stable_value(value) for value in values}) > 1
        value = values[0]
        if isinstance(default, dict):
            value = dict(value) if isinstance(value, dict) else {}
        elif isinstance(default, str):
            value = str(value or "")
        return CanonicalReadResult(value, len(rows), ambiguous)

    def _compare_shadow(
        self,
        surface: str,
        chat_id: int,
        legacy: Any,
        canonical_loader: Callable[[str], CanonicalReadResult],
    ) -> Any:
        if not self._sampled(chat_id, surface):
            if self.enabled:
                self.telemetry.record_canonical_read(
                    surface=surface,
                    outcome="sample_skipped",
                    latency_ms=0,
                    legacy_items=self._cardinality(legacy),
                    canonical_items=0,
                    compared=False,
                )
            return legacy

        started = time.perf_counter()
        try:
            candidates = self._identity_candidates(chat_id)
        except Exception:
            self.telemetry.record_canonical_read(
                surface=surface,
                outcome="identity_error",
                latency_ms=int((time.perf_counter() - started) * 1000),
                legacy_items=self._cardinality(legacy),
                canonical_items=0,
                compared=False,
            )
            return legacy

        if len(candidates) == 0:
            self.telemetry.record_canonical_read(
                surface=surface,
                outcome="identity_unresolved",
                latency_ms=int((time.perf_counter() - started) * 1000),
                legacy_items=self._cardinality(legacy),
                canonical_items=0,
                compared=False,
            )
            return legacy
        if len(candidates) != 1:
            self.telemetry.record_canonical_read(
                surface=surface,
                outcome="identity_conflict",
                latency_ms=int((time.perf_counter() - started) * 1000),
                legacy_items=self._cardinality(legacy),
                canonical_items=0,
                compared=False,
            )
            return legacy

        try:
            canonical = canonical_loader(candidates[0])
        except Exception:
            self.telemetry.record_canonical_read(
                surface=surface,
                outcome="canonical_error",
                latency_ms=int((time.perf_counter() - started) * 1000),
                legacy_items=self._cardinality(legacy),
                canonical_items=0,
                compared=False,
            )
            return legacy

        outcome = (
            "canonical_ambiguous"
            if canonical.ambiguous
            else self._classify(legacy, canonical.value)
        )
        self.telemetry.record_canonical_read(
            surface=surface,
            outcome=outcome,
            latency_ms=int((time.perf_counter() - started) * 1000),
            legacy_items=self._cardinality(legacy),
            canonical_items=canonical.row_count,
            compared=True,
        )
        return legacy

    def get(self, chat_id: int) -> list[dict]:
        legacy = list(self.primary.get(chat_id) or [])

        def load(owner_id: str) -> CanonicalReadResult:
            rows = self._canonical_rows(
                "bco_messages",
                owner_id,
                select="role,content,created_at",
                order="id.desc",
                limit=self.primary.memory_max_turns * 2,
            )
            rows.reverse()
            value = [
                {
                    "role": str(row.get("role") or ""),
                    "content": str(row.get("content") or ""),
                }
                for row in rows
            ]
            return CanonicalReadResult(value, len(rows))

        return self._compare_shadow("messages", chat_id, legacy, load)

    def get_profile(self, chat_id: int) -> dict[str, Any]:
        legacy = dict(self.primary.get_profile(chat_id) or {})
        return self._compare_shadow(
            "profile",
            chat_id,
            legacy,
            lambda owner_id: self._canonical_player_field(
                owner_id,
                "profile",
                default={},
            ),
        )

    def get_summary(self, chat_id: int) -> str:
        legacy = str(self.primary.get_summary(chat_id) or "")
        return self._compare_shadow(
            "summary",
            chat_id,
            legacy,
            lambda owner_id: self._canonical_player_field(
                owner_id,
                "summary",
                default="",
            ),
        )

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        legacy = dict(self.primary.get_derived_intelligence(chat_id) or {})
        return self._compare_shadow(
            "derived_intelligence",
            chat_id,
            legacy,
            lambda owner_id: self._canonical_player_field(
                owner_id,
                "derived",
                default={},
            ),
        )

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        legacy = list(self.primary.list_mistake_stats(chat_id) or [])

        def load(owner_id: str) -> CanonicalReadResult:
            rows = self._canonical_rows(
                "bco_player_mistakes",
                owner_id,
                select=(
                    "mistake_key,label,count,first_seen,last_seen,evidence"
                ),
                order="count.desc,last_seen.desc",
                limit=20,
            )
            return CanonicalReadResult(rows, len(rows))

        return self._compare_shadow("mistakes", chat_id, legacy, load)

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return [
            str(item.get("label") or "")
            for item in self.list_mistake_stats(chat_id)
            if item.get("label")
        ]

    def list_episodes(self, chat_id: int, limit: int = 20) -> list[dict]:
        bounded_limit = max(1, min(int(limit), 100))
        legacy = list(self.primary.list_episodes(chat_id, bounded_limit) or [])

        def load(owner_id: str) -> CanonicalReadResult:
            rows = self._canonical_rows(
                "bco_episodes",
                owner_id,
                select="kind,data,created_at",
                order="id.desc",
                limit=bounded_limit,
            )
            value = [
                dict(
                    row.get("data") if isinstance(row.get("data"), dict) else {},
                    kind=row.get("kind"),
                    created_at=row.get("created_at"),
                )
                for row in rows
            ]
            return CanonicalReadResult(value, len(rows))

        return self._compare_shadow("episodes", chat_id, legacy, load)

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        legacy = list(self.primary.list_training_sessions(chat_id) or [])

        def load(owner_id: str) -> CanonicalReadResult:
            rows = self._canonical_rows(
                "bco_training_sessions",
                owner_id,
                select="data,created_at",
                order="id.desc",
                limit=50,
            )
            value = [
                dict(
                    row.get("data") if isinstance(row.get("data"), dict) else {},
                    created_at=row.get("created_at"),
                )
                for row in rows
            ]
            return CanonicalReadResult(value, len(rows))

        return self._compare_shadow("training_sessions", chat_id, legacy, load)

    def list_progression_events(self, chat_id: int) -> list[dict]:
        legacy = list(self.primary.list_progression_events(chat_id) or [])

        def load(owner_id: str) -> CanonicalReadResult:
            rows = self._canonical_rows(
                "bco_progression_events",
                owner_id,
                select="data,created_at",
                order="id.desc",
                limit=100,
            )
            value = [
                dict(
                    row.get("data") if isinstance(row.get("data"), dict) else {},
                    created_at=row.get("created_at"),
                )
                for row in rows
            ]
            return CanonicalReadResult(value, len(rows))

        return self._compare_shadow("progression_events", chat_id, legacy, load)
