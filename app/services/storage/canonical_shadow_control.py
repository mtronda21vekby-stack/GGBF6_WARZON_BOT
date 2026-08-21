# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.observability.quality import QualityTelemetry, quality_telemetry
from app.services.storage.canonical_shadow import CanonicalReadShadowStore


class CanonicalReadShadowControlStore:
    """Service-owned runtime control for comparison-only canonical reads.

    The persistent adapter remains the legacy read authority. The inner shadow
    store runs only when local configuration and the database flag are enabled.
    Any control lookup failure falls back to one established legacy read.
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
        self._database_enabled: bool | None = None
        self._flag_reason = ""
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

    def _cache_fresh(self) -> bool:
        with self._lock:
            return (
                self._database_enabled is not None
                and time.monotonic() - self._flag_checked_monotonic
                < self.flag_ttl_s
            )

    def _publish_control(self) -> None:
        with self._lock:
            enabled = self._database_enabled
            reason = self._flag_reason
            checked_at = self._flag_checked_at
            error = self._control_error
        self.telemetry.configure_canonical_read_control(
            database_enabled=enabled,
            reason=reason,
            checked_at=checked_at,
            error=error,
        )

    def _refresh_database_flag(self) -> bool:
        if not self.shadow.enabled or self.shadow.sample_rate <= 0.0:
            with self._lock:
                self._database_enabled = None
                self._flag_reason = "local_shadow_disabled"
                self._flag_checked_at = self._now_iso()
                self._flag_checked_monotonic = time.monotonic()
                self._control_error = ""
            self._publish_control()
            return False

        if self._cache_fresh():
            with self._lock:
                return bool(self._database_enabled)

        try:
            response = self.legacy._request(
                "GET",
                "black_crown_ownership_runtime_flags",
                params={
                    "flag_key": "eq.canonical_shadow_read",
                    "select": "enabled,reason,updated_at",
                    "limit": "1",
                },
            )
            rows = self.legacy._rows(response)
            row = rows[0] if rows else {}
            enabled = bool(row.get("enabled", False))
            reason = str(
                row.get("reason")
                or ("enabled" if enabled else "flag_missing_or_disabled")
            )[:128]
            updated_at = str(row.get("updated_at") or "")[:64]
            error = ""
        except Exception as exc:
            enabled = False
            reason = "control_lookup_failed"
            updated_at = ""
            error = type(exc).__name__[:64]

        with self._lock:
            self._database_enabled = enabled
            self._flag_reason = reason
            self._flag_updated_at = updated_at
            self._flag_checked_at = self._now_iso()
            self._flag_checked_monotonic = time.monotonic()
            self._control_error = error
        self._publish_control()
        return enabled

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
                    "schema": "bco-canonical-read-shadow-v1",
                    "database_enabled": self._database_enabled,
                    "control_reason": self._flag_reason,
                    "control_updated_at": self._flag_updated_at or None,
                    "control_checked_at": self._flag_checked_at or None,
                    "control_error": self._control_error,
                    "control_flag_ttl_s": self.flag_ttl_s,
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
