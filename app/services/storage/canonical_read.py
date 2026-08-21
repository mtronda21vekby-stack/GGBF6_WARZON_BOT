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

    Canonical reads are permitted only when the server status contract proves
    schema compatibility, zero identity conflicts and complete projection for
    the requested table. Any missing evidence fails closed to the exact legacy
    subject rather than returning a partial canonical history.
    """

    SCHEMA_VERSION = "bco-canonical-read-v1"
    RUNTIME_SCHEMA = "bco-canonical-owner-v3"

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
        self._control_cache: dict[str, Any] = self._empty_control(
            state="not_loaded"
        )
        self._owner_cache: dict[int, tuple[float, CanonicalOwnerResolution]] = {}
        self._totals: Counter[str] = Counter()
        self._by_table: dict[str, Counter[str]] = defaultdict(Counter)

    @classmethod
    def _empty_control(
        cls,
        *,
        state: str,
        last_error: str = "",
    ) -> dict[str, Any]:
        return {
            "expires_at": 0.0,
            "database_flag_enabled": False,
            "effective_enabled": False,
            "state": str(state or "unavailable")[:64],
            "updated_at": "",
            "last_error": str(last_error or "")[:64],
            "runtime_schema": "",
            "read_schema": "",
            "coverage": {},
            "mapping_conflicts": 0,
            "merge_pending": 0,
        }

    def _record(self, table: str, outcome: str) -> None:
        safe_table = str(table or "unknown")[:64]
        safe_outcome = str(outcome or "unknown")[:64]
        with self._lock:
            self._totals[safe_outcome] += 1
            self._by_table[safe_table][safe_outcome] += 1

    @staticmethod
    def _content_range_count(response: Any, fallback_rows: list[dict]) -> int:
        content_range = str(
            getattr(response, "headers", {}).get("content-range", "") or ""
        )
        if "/" in content_range:
            tail = content_range.rsplit("/", 1)[-1]
            if tail.isdigit():
                return int(tail)
        return len(fallback_rows)

    @staticmethod
    def _safe_nonnegative_int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def _control_state(self, *, refresh: bool = False) -> dict[str, Any]:
        """Read privacy-safe server control state; never expose flag reason."""
        if not self.capability_enabled:
            return self._empty_control(state="capability_disabled")

        now = time.monotonic()
        with self._lock:
            cached = dict(self._control_cache)
        if not refresh and now < float(cached.get("expires_at") or 0.0):
            return cached

        control = self._empty_control(state="status_missing")
        try:
            response = self._request(
                "GET",
                "black_crown_ownership_runtime_status",
                params={
                    "select": (
                        "schema_version,canonical_dual_read_enabled,"
                        "canonical_dual_read_updated_at,canonical_read_schema,"
                        "coverage,mapping_state"
                    ),
                    "limit": "1",
                },
            )
            rows = self._rows(response)
            if rows:
                raw = dict(rows[0])
                database_flag_enabled = bool(
                    raw.get("canonical_dual_read_enabled", False)
                )
                runtime_schema = str(raw.get("schema_version") or "")[:64]
                read_schema = str(raw.get("canonical_read_schema") or "")[:64]
                updated_at = str(
                    raw.get("canonical_dual_read_updated_at") or ""
                )[:64]

                coverage: dict[str, dict[str, int]] = {}
                raw_coverage = raw.get("coverage")
                if isinstance(raw_coverage, dict):
                    for table, values in list(raw_coverage.items())[:64]:
                        if not isinstance(values, dict):
                            continue
                        coverage[str(table)[:64]] = {
                            "total_rows": self._safe_nonnegative_int(
                                values.get("total_rows")
                            ),
                            "canonical_rows": self._safe_nonnegative_int(
                                values.get("canonical_rows")
                            ),
                            "legacy_only_rows": self._safe_nonnegative_int(
                                values.get("legacy_only_rows")
                            ),
                        }

                raw_mapping = raw.get("mapping_state")
                mapping = raw_mapping if isinstance(raw_mapping, dict) else {}
                mapping_conflicts = self._safe_nonnegative_int(
                    mapping.get("conflict")
                )
                merge_pending = self._safe_nonnegative_int(
                    mapping.get("merge_pending")
                )

                schema_ok = (
                    runtime_schema == self.RUNTIME_SCHEMA
                    and read_schema == self.SCHEMA_VERSION
                )
                mapping_ok = mapping_conflicts == 0 and merge_pending == 0
                effective_enabled = (
                    database_flag_enabled and schema_ok and mapping_ok
                )

                if not schema_ok:
                    state = "schema_mismatch"
                elif not mapping_ok:
                    state = "mapping_conflict"
                elif database_flag_enabled:
                    state = "database_enabled"
                else:
                    state = "database_disabled"

                control = {
                    "expires_at": now + self.flag_cache_ttl_s,
                    "database_flag_enabled": database_flag_enabled,
                    "effective_enabled": effective_enabled,
                    "state": state,
                    "updated_at": updated_at,
                    "last_error": "",
                    "runtime_schema": runtime_schema,
                    "read_schema": read_schema,
                    "coverage": coverage,
                    "mapping_conflicts": mapping_conflicts,
                    "merge_pending": merge_pending,
                }
        except Exception as exc:
            error_class = type(exc).__name__
            control = self._empty_control(
                state="status_lookup_failed",
                last_error=error_class,
            )
            control["expires_at"] = now + self.flag_cache_ttl_s
            log.warning(
                "canonical read status lookup failed error=%s",
                error_class,
            )

        if not control.get("expires_at"):
            control["expires_at"] = now + self.flag_cache_ttl_s
        with self._lock:
            self._control_cache = dict(control)
        return dict(control)

    def _table_parity(
        self,
        control: Mapping[str, Any],
        table: str,
    ) -> tuple[bool, str]:
        raw_coverage = control.get("coverage")
        coverage = raw_coverage if isinstance(raw_coverage, dict) else {}
        values = coverage.get(str(table))
        if not isinstance(values, dict):
            return False, "coverage_missing"

        total_rows = self._safe_nonnegative_int(values.get("total_rows"))
        canonical_rows = self._safe_nonnegative_int(
            values.get("canonical_rows")
        )
        legacy_only_rows = self._safe_nonnegative_int(
            values.get("legacy_only_rows")
        )
        if legacy_only_rows != 0 or canonical_rows != total_rows:
            return False, "coverage_incomplete"
        return True, "coverage_complete"

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
            candidate_count = self._safe_nonnegative_int(
                raw.get("candidate_count")
            )
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
        except Exception as exc:
            log.warning(
                "canonical read owner lookup failed error=%s",
                type(exc).__name__,
            )

        cache_ttl = (
            min(self.identity_cache_ttl_s, self.flag_cache_ttl_s)
            if resolution.state == "error"
            else self.identity_cache_ttl_s
        )
        with self._lock:
            self._owner_cache[subject] = (now + cache_ttl, resolution)
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
        control = self._control_state()
        if not bool(control.get("effective_enabled", False)):
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason=str(control.get("state") or "control_unavailable"),
            )

        parity_ok, parity_state = self._table_parity(control, table)
        if not parity_ok:
            return self._legacy_rows(
                table,
                telegram_user_id,
                params,
                legacy_column=legacy_column,
                reason=parity_state,
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
        control = self._control_state()
        effective_enabled = bool(control.get("effective_enabled", False))
        parity_ok, parity_state = self._table_parity(control, table)
        resolution = (
            self._owner_resolution(telegram_user_id)
            if effective_enabled and parity_ok
            else CanonicalOwnerResolution(state="disabled")
        )

        if effective_enabled and parity_ok and resolution.state == "resolved":
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
        elif effective_enabled and parity_ok:
            self._record(table, f"canonical_count_{resolution.state}")

        if not effective_enabled:
            fallback_reason = str(
                control.get("state") or "control_unavailable"
            )
        elif not parity_ok:
            fallback_reason = parity_state
        else:
            fallback_reason = "canonical_count_fallback"
        self._record(table, f"legacy_count_{fallback_reason}")
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
        control = self._control_state(refresh=refresh_flag)
        raw_coverage = control.get("coverage")
        coverage = raw_coverage if isinstance(raw_coverage, dict) else {}
        ready_tables: list[str] = []
        blocked_tables: list[str] = []
        for table in sorted(coverage)[:64]:
            parity_ok, _ = self._table_parity(control, table)
            (ready_tables if parity_ok else blocked_tables).append(table[:64])

        with self._lock:
            totals = dict(self._totals)
            by_table = {
                table: dict(counter)
                for table, counter in sorted(self._by_table.items())
            }
            owner_cache_entries = len(self._owner_cache)

        control_state = str(control.get("state") or "unavailable")[:64]
        effective_enabled = bool(control.get("effective_enabled", False))
        return {
            "schema_version": self.SCHEMA_VERSION,
            "runtime_schema": str(control.get("runtime_schema") or "")[:64],
            "capability_enabled": self.capability_enabled,
            "database_flag_enabled": bool(
                control.get("database_flag_enabled", False)
            ),
            "effective_enabled": effective_enabled,
            "mode": "canonical_first" if effective_enabled else "legacy",
            "control_state": control_state,
            # Compatibility alias consumed by the current readiness serializer;
            # this is a stable code, never the database operator reason.
            "flag_reason": control_state,
            "flag_updated_at": str(control.get("updated_at") or "")[:64] or None,
            "last_control_error": str(
                control.get("last_error") or ""
            )[:64],
            "mapping_conflicts": self._safe_nonnegative_int(
                control.get("mapping_conflicts")
            ),
            "merge_pending": self._safe_nonnegative_int(
                control.get("merge_pending")
            ),
            "coverage_ready_tables": ready_tables,
            "coverage_blocked_tables": blocked_tables,
            "canonical_hits": int(totals.get("canonical_hit", 0)),
            "canonical_misses": int(totals.get("canonical_miss", 0)),
            "canonical_ambiguous": int(totals.get("canonical_ambiguous", 0)),
            "canonical_query_errors": int(
                totals.get("canonical_query_error", 0)
            ),
            "canonical_count_hits": int(
                totals.get("canonical_count_hit", 0)
            ),
            "canonical_count_misses": int(
                totals.get("canonical_count_miss", 0)
            ),
            "canonical_count_errors": int(
                totals.get("canonical_count_error", 0)
            ),
            "legacy_fallbacks": int(
                sum(
                    count
                    for outcome, count in totals.items()
                    if outcome.startswith("legacy_fallback_")
                    or outcome.startswith("legacy_count_")
                )
            ),
            "coverage_incomplete_fallbacks": int(
                totals.get("legacy_fallback_coverage_incomplete", 0)
                + totals.get("legacy_count_coverage_incomplete", 0)
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
