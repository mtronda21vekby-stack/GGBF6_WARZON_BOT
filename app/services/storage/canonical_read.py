# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Mapping


log = logging.getLogger("bco.storage.canonical_read")


@dataclass(frozen=True)
class CanonicalOwnerResolution:
    state: str
    black_crown_user_id: str = ""
    candidate_count: int = 0


class CanonicalReadRouter:
    """Server-owned canonical-first read selector with legacy fallback.

    The caller supplies only the verified Telegram subject already used by the
    legacy storage API. Canonical identity is resolved through a service-role
    RPC; browser/profile supplied owner IDs never enter this boundary.
    """

    SCHEMA_VERSION = "bco-canonical-read-v1"

    def __init__(
        self,
        *,
        request: Callable[..., Any],
        rows: Callable[[Any], list[dict]],
        capability_enabled: bool = True,
        flag_cache_ttl_s: float = 15.0,
        identity_cache_ttl_s: float = 120.0,
    ) -> None:
        self._request = request
        self._rows = rows
        self.capability_enabled = bool(capability_enabled)
        self.flag_cache_ttl_s = max(1.0, float(flag_cache_ttl_s or 15.0))
        self.identity_cache_ttl_s = max(1.0, float(identity_cache_ttl_s or 120.0))
        self._lock = threading.RLock()
        self._flag_cache: dict[str, Any] = {
            "expires_at": 0.0,
            "enabled": False,
            "reason": "not_loaded",
            "updated_at": "",
            "last_error": "",
        }
        self._owner_cache: dict[int, tuple[float, CanonicalOwnerResolution]] = {}
        self._totals: Counter[str] = Counter()
        self._by_table: dict[str, Counter[str]] = defaultdict(Counter)

    def _record(self, table: str, outcome: str) -> None:
        safe_table = str(table or "unknown")[:64]
        safe_outcome = str(outcome or "unknown")[:64]
        with self._lock:
            self._totals[safe_outcome] += 1
            self._by_table[safe_table][safe_outcome] += 1

    @staticmethod
    def _content_range_count(response: Any, fallback_rows: list[dict]) -> int:
        content_range = str(getattr(response, "headers", {}).get("content-range", "") or "")
        if "/" in content_range:
            tail = content_range.rsplit("/", 1)[-1]
            if tail.isdigit():
                return int(tail)
        return len(fallback_rows)

    def _flag_state(self, *, refresh: bool = False) -> tuple[bool, str, str, str]:
        if not self.capability_enabled:
            return False, "capability_disabled", "", ""

        now = time.monotonic()
        with self._lock:
            cached = dict(self._flag_cache)
        if not refresh and now < float(cached.get("expires_at") or 0.0):
            return (
                bool(cached.get("enabled", False)),
                str(cached.get("reason") or "flag_disabled"),
                str(cached.get("updated_at") or ""),
                str(cached.get("last_error") or ""),
            )

        enabled = False
        reason = "flag_missing"
        updated_at = ""
        last_error = ""
        try:
            response = self._request(
                "GET",
                "black_crown_ownership_runtime_flags",
                params={
                    "flag_key": "eq.canonical_dual_read",
                    "select": "enabled,reason,updated_at",
                    "limit": "1",
                },
            )
            rows = self._rows(response)
            if rows:
                enabled = bool(rows[0].get("enabled", False))
                reason = str(rows[0].get("reason") or "flag_disabled")[:512]
                updated_at = str(rows[0].get("updated_at") or "")[:64]
        except Exception as exc:
            last_error = type(exc).__name__
            reason = "flag_lookup_failed"
            log.warning("canonical read flag lookup failed error=%s", last_error)

        with self._lock:
            self._flag_cache = {
                "expires_at": now + self.flag_cache_ttl_s,
                "enabled": enabled,
                "reason": reason,
                "updated_at": updated_at,
                "last_error": last_error,
            }
        return enabled, reason, updated_at, last_error

    def _owner_resolution(self, telegram_user_id: int) -> CanonicalOwnerResolution:
        subject = int(telegram_user_id)
        now = time.monotonic()
        with self._lock:
            cached = self._owner_cache.get(subject)
        if cached and now < cached[0]:
            return cached[1]

        resolution = CanonicalOwnerResolution(state="error")
        try:
            response = self._request(
                "POST",
                "rpc/black_crown_resolve_read_owner",
                json={"p_provider": "telegram", "p_subject": str(subject)},
            )
            rows = self._rows(response)
            raw = dict(rows[0]) if rows else {}
            state = str(raw.get("resolution_state") or "unresolved")
            owner = str(raw.get("black_crown_user_id") or "")
            candidate_count = max(0, int(raw.get("candidate_count") or 0))
            if state == "resolved" and owner and candidate_count == 1:
                resolution = CanonicalOwnerResolution(
                    state="resolved",
                    black_crown_user_id=owner,
                    candidate_count=1,
                )
            elif state in {"unresolved", "conflict"}:
                resolution = CanonicalOwnerResolution(
                    state=state,
                    candidate_count=candidate_count,
                )
            else:
                resolution = CanonicalOwnerResolution(state="error")
        except Exception as exc:
            log.warning("canonical read owner lookup failed error=%s", type(exc).__name__)
            resolution = CanonicalOwnerResolution(state="error")

        with self._lock:
            self._owner_cache[subject] = (
                now + self.identity_cache_ttl_s,
                resolution,
            )
        return resolution

    def prime_telegram_identity(
        self,
        telegram_user_id: int,
        identity: Mapping[str, Any] | None,
    ) -> None:
        raw = dict(identity or {})
        owner = str(raw.get("black_crown_user_id") or "")
        identity_status = str(raw.get("identity_status") or "")
        account_status = str(raw.get("account_status") or "")
        if not owner:
            return
        if identity_status not in {"active", "provisional"}:
            return
        if account_status not in {"active", "provisional"}:
            return
        with self._lock:
            self._owner_cache[int(telegram_user_id)] = (
                time.monotonic() + self.identity_cache_ttl_s,
                CanonicalOwnerResolution(
                    state="resolved",
                    black_crown_user_id=owner,
                    candidate_count=1,
                ),
            )

    def _legacy_rows(
        self,
        table: str,
        telegram_user_id: int,
        params: Mapping[str, Any],
        *,
        legacy_column: str,
        reason: str,
    ) -> list[dict]:
        legacy_params = dict(params)
        legacy_params[legacy_column] = f"eq.{int(telegram_user_id)}"
        self._record(table, f"legacy_fallback_{reason}")
        return self._rows(self._request("GET", table, params=legacy_params))

    def select_rows(
        self,
        table: str,
        telegram_user_id: int,
        *,
        params: Mapping[str, Any],
        legacy_column: str = "chat_id",
        singleton: bool = False,
    ) -> list[dict]:
        enabled, flag_reason, _, flag_error = self._flag_state()
        if not enabled:
            reason = "flag_error" if flag_error else flag_reason
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason=reason,
            )

        resolution = self._owner_resolution(telegram_user_id)
        if resolution.state != "resolved":
            reason = {
                "unresolved": "identity_unresolved",
                "conflict": "identity_conflict",
            }.get(resolution.state, "identity_error")
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason=reason,
            )

        canonical_params = dict(params)
        canonical_params["black_crown_user_id"] = (
            f"eq.{resolution.black_crown_user_id}"
        )
        if singleton:
            canonical_params["limit"] = "2"

        try:
            canonical_rows = self._rows(
                self._request("GET", table, params=canonical_params)
            )
        except Exception as exc:
            self._record(table, "canonical_query_error")
            log.warning(
                "canonical read query failed table=%s error=%s",
                str(table or "unknown")[:64],
                type(exc).__name__,
            )
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason="canonical_query_error",
            )

        if singleton and len(canonical_rows) > 1:
            self._record(table, "canonical_ambiguous")
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason="canonical_ambiguous",
            )
        if not canonical_rows:
            self._record(table, "canonical_miss")
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason="canonical_miss",
            )

        self._record(table, "canonical_hit")
        return canonical_rows

    def count(
        self,
        table: str,
        telegram_user_id: int,
        *,
        select_column: str = "id",
        legacy_column: str = "chat_id",
    ) -> int:
        enabled, flag_reason, _, flag_error = self._flag_state()
        resolution = (
            self._owner_resolution(telegram_user_id)
            if enabled
            else CanonicalOwnerResolution(state="disabled")
        )

        if enabled and resolution.state == "resolved":
            try:
                response = self._request(
                    "GET",
                    table,
                    params={
                        "black_crown_user_id": (
                            f"eq.{resolution.black_crown_user_id}"
                        ),
                        "select": select_column,
                        "limit": "1",
                    },
                    extra_headers={"Prefer": "count=exact"},
                )
                rows = self._rows(response)
                total = self._content_range_count(response, rows)
                if total > 0:
                    self._record(table, "canonical_count_hit")
                    return total
                self._record(table, "canonical_count_miss")
            except Exception as exc:
                self._record(table, "canonical_count_error")
                log.warning(
                    "canonical count failed table=%s error=%s",
                    str(table or "unknown")[:64],
                    type(exc).__name__,
                )
        elif enabled:
            self._record(table, f"canonical_count_{resolution.state}")

        legacy_reason = (
            "flag_error"
            if flag_error
            else flag_reason
            if not enabled
            else "canonical_count_fallback"
        )
        self._record(table, f"legacy_count_{legacy_reason}")
        response = self._request(
            "GET",
            table,
            params={
                legacy_column: f"eq.{int(telegram_user_id)}",
                "select": select_column,
                "limit": "1",
            },
            extra_headers={"Prefer": "count=exact"},
        )
        return self._content_range_count(response, self._rows(response))

    def snapshot(self, *, refresh_flag: bool = True) -> dict[str, Any]:
        enabled, reason, updated_at, last_error = self._flag_state(
            refresh=refresh_flag
        )
        with self._lock:
            totals = dict(self._totals)
            by_table = {
                table: dict(counter)
                for table, counter in sorted(self._by_table.items())
            }
            owner_cache_entries = len(self._owner_cache)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "capability_enabled": self.capability_enabled,
            "database_flag_enabled": enabled,
            "mode": "canonical_first" if enabled else "legacy",
            "flag_reason": reason[:512],
            "flag_updated_at": updated_at[:64] or None,
            "last_control_error": last_error[:64],
            "canonical_hits": int(totals.get("canonical_hit", 0)),
            "canonical_misses": int(totals.get("canonical_miss", 0)),
            "canonical_ambiguous": int(totals.get("canonical_ambiguous", 0)),
            "canonical_query_errors": int(
                totals.get("canonical_query_error", 0)
            ),
            "legacy_fallbacks": int(
                sum(
                    count
                    for outcome, count in totals.items()
                    if outcome.startswith("legacy_fallback_")
                    or outcome.startswith("legacy_count_")
                )
            ),
            "identity_unresolved_fallbacks": int(
                totals.get("legacy_fallback_identity_unresolved", 0)
            ),
            "identity_conflict_fallbacks": int(
                totals.get("legacy_fallback_identity_conflict", 0)
            ),
            "owner_cache_entries": owner_cache_entries,
            "by_table": by_table,
        }
