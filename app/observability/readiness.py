# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from app.observability.quality import quality_telemetry


def readiness_snapshot(
    settings: Any,
    store: Any,
    *,
    app_version: str = "unknown",
    release_contract: str = "unknown",
    usage_guard: Any = None,
    replay_guard: Any = None,
) -> dict:
    """Privacy-safe runtime readiness. Never exposes secret values/content."""
    ai_enabled = bool(getattr(settings, "ai_enabled", True))
    ai_configured = bool(str(getattr(settings, "openai_api_key", "") or "").strip())
    supabase_secret = bool(str(getattr(settings, "supabase_service_role_key", "") or "").strip())
    supabase_url = bool(str(getattr(settings, "supabase_url", "") or "").strip())
    storage_class = type(store).__name__ if store is not None else "None"

    recovery: dict[str, Any] = {}
    recovery_fn = getattr(store, "recovery_status", None)
    if callable(recovery_fn):
        try:
            raw = dict(recovery_fn() or {})
            recovery = {
                "primary_available": bool(raw.get("primary_available", False)),
                "outbox_pending": int(raw.get("outbox_pending") or 0),
                "outbox_replayed": int(raw.get("outbox_replayed") or 0),
                "outbox_dropped": int(raw.get("outbox_dropped") or 0),
                "last_primary_error": str(raw.get("last_primary_error") or "")[:64],
                "outbox_max": int(raw.get("outbox_max") or 0),
                "last_probe_ok": raw.get("last_probe_ok") if isinstance(raw.get("last_probe_ok"), bool) else None,
                "last_probe_at": str(raw.get("last_probe_at") or "")[:64],
                "probe_successes": int(raw.get("probe_successes") or 0),
                "probe_failures": int(raw.get("probe_failures") or 0),
            }
        except Exception:
            recovery = {"status": "unavailable"}

    guard_snapshot: dict[str, Any] = {}
    if usage_guard is not None and callable(getattr(usage_guard, "snapshot", None)):
        try:
            guard_snapshot = dict(usage_guard.snapshot() or {})
        except Exception:
            guard_snapshot = {"status": "unavailable"}

    replay_snapshot: dict[str, Any] = {}
    if replay_guard is not None and callable(getattr(replay_guard, "snapshot", None)):
        try:
            replay_snapshot = dict(replay_guard.snapshot() or {})
        except Exception:
            replay_snapshot = {"status": "unavailable"}

    features = {
        "ai": ai_enabled and ai_configured,
        "persistent_memory_configured": supabase_secret and supabase_url,
        "live_knowledge": bool(getattr(settings, "live_knowledge_enabled", True)),
        "vod": bool(getattr(settings, "vod_enabled", True)),
        "voice": bool(getattr(settings, "voice_enabled", True)),
        "mini_app": True,
        "command_center": True,
        "persistence_recovery": bool(recovery_fn),
        "storage_startup_probe": callable(getattr(store, "probe_primary", None)),
        "abuse_guard": bool(getattr(settings, "usage_guard_enabled", True)),
        "telegram_replay_dedupe": replay_guard is not None,
    }
    primary_degraded = bool(recovery) and recovery.get("primary_available") is False
    probe_failed = bool(recovery) and recovery.get("last_probe_ok") is False
    required_ok = features["ai"]
    status = "degraded" if (not required_ok or primary_degraded or probe_failed) else "ready"
    return {
        "ok": required_ok,
        "status": status,
        "release": {
            "version": str(app_version or "unknown")[:32],
            "contract": str(release_contract or "unknown")[:64],
        },
        "storage": {
            "configured_mode": str(getattr(settings, "storage_backend", "auto") or "auto")[:32],
            "active_adapter": storage_class[:64],
            "persistent_configured": features["persistent_memory_configured"],
            "resilient_fallback": "Resilient" in storage_class,
            "recovery": recovery,
        },
        "features": features,
        "abuse_guard": {
            "usage": guard_snapshot,
            "telegram_replay": replay_snapshot,
            "telegram_max_update_bytes": int(getattr(settings, "telegram_max_update_bytes", 0) or 0),
        },
        "quality": quality_telemetry.snapshot(),
    }
