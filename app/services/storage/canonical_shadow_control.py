# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from app.observability.quality import QualityTelemetry, quality_telemetry
from app.services.storage.canonical_shadow import CanonicalReadShadowStore


_EXPECTED_STATUS_SCHEMA = "bco-canonical-read-shadow-v2"
_ALLOWED_PROMOTION_BLOCKERS = {
    "shadow_disabled",
    "dual_write_disabled",
    "identity_conflict",
    "merge_pending",
    "coverage_incomplete",
    "schema_mismatch",
    "control_error",
}


class CanonicalReadShadowControlStore:
    """Service-owned runtime control for comparison-only canonical reads.

    The persistent adapter remains the legacy read authority. The inner shadow
    store runs only when local configuration and a privacy-safe database status
    contract are enabled. Schema mismatch, disabled dual-write, any conflict,
    merge-pending state or control lookup failure fails closed to one established
    legacy read. Coverage incompleteness remains observable shadow evidence but
    blocks promotion readiness.
    """

    def __init__(
        self,
        shadow: CanonicalReadShadowStore,
        *,
        flag_ttl_s: float = 30.0,
        telemetry: QualityTelemetry | None = None,
    ) -> None:
        self.shadow = shadow
        self.legacy = shadow.primary
        self.flag_ttl_s = max(1.0, float(flag_ttl_s or 30.0))
        self.telemetry = telemetry or shadow.telemetry or quality_telemetry
        self._lock = threading.RLock()
        self._database_flag_enabled: bool | None = None
        self._effective_enabled: bool | None = None
        self._control_state = "not_checked"
        self._schema_version = ""
        self._dual_write_enabled = False
        self._resolved_count = 0
        self._unresolved_count = 0
        self._conflict_count = 0
        self._merge_pending_count = 0
        self._coverage_ready = False
        self._promotion_ready = False
        self._promotion_blockers: tuple[str, ...] = ()
        self._flag_updated_at = ""
        self._flag_checked_at = ""
        self._flag_checked_monotonic = 0.0
        self._control_error = ""

    def __getattr__(self, name: str) -> Any:
        return getattr(self.shadow, name)

    def close(self) -> None:
        self.shadow.close()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _cardinality(value: Any) -> int:
        if isinstance(value, (list, tuple, set, dict)):
            return len(value)
        return int(value not in (None, ""))

    @staticmethod
    def _safe_nonnegative_int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _sanitize_blockers(
        blockers: Iterable[Any] | None,
    ) -> tuple[str, ...]:
        safe = {
            str(item or "").strip().casefold()
            for item in (blockers or ())
        }
        return tuple(sorted(safe & _ALLOWED_PROMOTION_BLOCKERS))

    def _cache_fresh(self) -> bool:
        with self._lock:
            return (
                self._effective_enabled is not None
                and time.monotonic() - self._flag_checked_monotonic
                < self.flag_ttl_s
            )

    def _publish_control(self) -> None:
        with self._lock:
            enabled = self._effective_enabled
            state = self._control_state
            checked_at = self._flag_checked_at
            error = self._control_error
            promotion_ready = self._promotion_ready
            coverage_ready = self._coverage_ready
            blockers = self._promotion_blockers
            conflicts = self._conflict_count
            merge_pending = self._merge_pending_count
        self.telemetry.configure_canonical_read_control(
            database_enabled=enabled,
            reason=state,
            checked_at=checked_at,
            error=error,
            promotion_ready=promotion_ready,
            coverage_ready=coverage_ready,
            promotion_blockers=blockers,
            conflict_count=conflicts,
            merge_pending_count=merge_pending,
        )

    def _set_local_disabled(self) -> None:
        with self._lock:
            self._database_flag_enabled = None
            self._effective_enabled = None
            self._control_state = "local_shadow_disabled"
            self._schema_version = ""
            self._dual_write_enabled = False
            self._resolved_count = 0
            self._unresolved_count = 0
            self._conflict_count = 0
            self._merge_pending_count = 0
            self._coverage_ready = False
            self._promotion_ready = False
            self._promotion_blockers = ("shadow_disabled",)
            self._flag_updated_at = ""
            self._flag_checked_at = self._now_iso()
            self._flag_checked_monotonic = time.monotonic()
            self._control_error = ""

    def _refresh_database_flag(self) -> bool:
        if not self.shadow.enabled or self.shadow.sample_rate <= 0.0:
            self._set_local_disabled()
            self._publish_control()
            return False

        if self._cache_fresh():
            with self._lock:
                return bool(self._effective_enabled)

        try:
            response = self.legacy._request(
                "GET",
                "black_crown_canonical_read_runtime_status",
                params={
                    "select": (
                        "schema_version,shadow_read_enabled,"
                        "shadow_read_updated_at,dual_write_enabled,"
                        "resolved_mappings,unresolved_mappings,"
                        "conflict_mappings,merge_pending_mappings,"
                        "shadow_surface_coverage_ready,promotion_ready,"
                        "promotion_blockers"
                    ),
                    "limit": "1",
                },
            )
            rows = self.legacy._rows(response)
            row = rows[0] if rows else {}

            schema_version = str(row.get("schema_version") or "")[:64]
            database_flag_enabled = bool(
                row.get("shadow_read_enabled", False)
            )
            dual_write_enabled = bool(row.get("dual_write_enabled", False))
            resolved_count = self._safe_nonnegative_int(
                row.get("resolved_mappings")
            )
            unresolved_count = self._safe_nonnegative_int(
                row.get("unresolved_mappings")
            )
            conflict_count = self._safe_nonnegative_int(
                row.get("conflict_mappings")
            )
            merge_pending_count = self._safe_nonnegative_int(
                row.get("merge_pending_mappings")
            )
            coverage_ready = bool(
                row.get("shadow_surface_coverage_ready", False)
            )
            database_promotion_ready = bool(
                row.get("promotion_ready", False)
            )
            blockers = self._sanitize_blockers(
                row.get("promotion_blockers")
                if isinstance(row.get("promotion_blockers"), list)
                else ()
            )
            updated_at = str(row.get("shadow_read_updated_at") or "")[:64]

            if schema_version != _EXPECTED_STATUS_SCHEMA:
                effective_enabled = False
                state = "schema_mismatch"
                blockers = tuple(sorted(set(blockers) | {"schema_mismatch"}))
            elif not database_flag_enabled:
                effective_enabled = False
                state = "database_disabled"
            elif not dual_write_enabled:
                effective_enabled = False
                state = "dual_write_disabled"
                blockers = tuple(
                    sorted(set(blockers) | {"dual_write_disabled"})
                )
            elif conflict_count > 0 or merge_pending_count > 0:
                effective_enabled = False
                state = "mapping_conflict"
                extra = set(blockers)
                if conflict_count > 0:
                    extra.add("identity_conflict")
                if merge_pending_count > 0:
                    extra.add("merge_pending")
                blockers = tuple(sorted(extra))
            else:
                effective_enabled = True
                state = "database_enabled"

            promotion_ready = bool(
                effective_enabled
                and coverage_ready
                and database_promotion_ready
                and not blockers
            )
            error = ""
        except Exception as exc:
            database_flag_enabled = False
            effective_enabled = False
            state = "control_lookup_failed"
            schema_version = ""
            dual_write_enabled = False
            resolved_count = 0
            unresolved_count = 0
            conflict_count = 0
            merge_pending_count = 0
            coverage_ready = False
            promotion_ready = False
            blockers = ("control_error",)
            updated_at = ""
            error = type(exc).__name__[:64]

        with self._lock:
            self._database_flag_enabled = database_flag_enabled
            self._effective_enabled = effective_enabled
            self._control_state = state
            self._schema_version = schema_version
            self._dual_write_enabled = dual_write_enabled
            self._resolved_count = resolved_count
            self._unresolved_count = unresolved_count
            self._conflict_count = conflict_count
            self._merge_pending_count = merge_pending_count
            self._coverage_ready = coverage_ready
            self._promotion_ready = promotion_ready
            self._promotion_blockers = blockers
            self._flag_updated_at = updated_at
            self._flag_checked_at = self._now_iso()
            self._flag_checked_monotonic = time.monotonic()
            self._control_error = error
        self._publish_control()
        return effective_enabled

    def _read(
        self,
        method: str,
        surface: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self._refresh_database_flag():
            return getattr(self.shadow, method)(*args, **kwargs)

        value = getattr(self.legacy, method)(*args, **kwargs)
        with self._lock:
            outcome = (
                "control_error"
                if self._control_error
                else self._control_state
                if self._control_state in {
                    "database_disabled",
                    "dual_write_disabled",
                    "mapping_conflict",
                    "schema_mismatch",
                }
                else "database_disabled"
            )
        if self.shadow.enabled and self.shadow.sample_rate > 0.0:
            self.telemetry.record_canonical_read(
                surface=surface,
                outcome=outcome,
                latency_ms=0,
                legacy_items=self._cardinality(value),
                canonical_items=0,
                compared=False,
            )
        return value

    def canonical_read_shadow_status(self) -> dict[str, Any]:
        self._refresh_database_flag()
        status = dict(self.shadow.canonical_read_shadow_status())
        with self._lock:
            status.update(
                {
                    "schema": _EXPECTED_STATUS_SCHEMA,
                    "database_enabled": self._effective_enabled,
                    "database_flag_enabled": self._database_flag_enabled,
                    # Compatibility field now contains only a stable state code.
                    "control_reason": self._control_state,
                    "control_state": self._control_state,
                    "control_schema_version": self._schema_version or None,
                    "control_updated_at": self._flag_updated_at or None,
                    "control_checked_at": self._flag_checked_at or None,
                    "control_error": self._control_error,
                    "control_flag_ttl_s": self.flag_ttl_s,
                    "dual_write_enabled": self._dual_write_enabled,
                    "resolved_mappings": self._resolved_count,
                    "unresolved_mappings": self._unresolved_count,
                    "identity_conflicts": self._conflict_count,
                    "merge_pending": self._merge_pending_count,
                    "coverage_ready": self._coverage_ready,
                    "promotion_ready": self._promotion_ready,
                    "promotion_blockers": list(
                        self._promotion_blockers
                    ),
                    "read_authority": "legacy",
                    "returns_legacy": True,
                    "canonical_returned_to_callers": False,
                    "canonical_primary_enabled": False,
                }
            )
        return status

    def get(self, chat_id: int) -> list[dict]:
        return list(self._read("get", "messages", chat_id) or [])

    def get_profile(self, chat_id: int) -> dict[str, Any]:
        return dict(self._read("get_profile", "profile", chat_id) or {})

    def get_summary(self, chat_id: int) -> str:
        return str(self._read("get_summary", "summary", chat_id) or "")

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        return dict(
            self._read(
                "get_derived_intelligence",
                "derived_intelligence",
                chat_id,
            )
            or {}
        )

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        return list(
            self._read("list_mistake_stats", "mistakes", chat_id) or []
        )

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return [
            str(item.get("label") or "")
            for item in self.list_mistake_stats(chat_id)
            if item.get("label")
        ]

    def list_episodes(self, chat_id: int, limit: int = 20) -> list[dict]:
        return list(
            self._read("list_episodes", "episodes", chat_id, limit) or []
        )

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        return list(
            self._read(
                "list_training_sessions",
                "training_sessions",
                chat_id,
            )
            or []
        )

    def list_progression_events(self, chat_id: int) -> list[dict]:
        return list(
            self._read(
                "list_progression_events",
                "progression_events",
                chat_id,
            )
            or []
        )
