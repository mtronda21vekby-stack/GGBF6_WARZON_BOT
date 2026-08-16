# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from app.observability.quality import quality_telemetry


def readiness_snapshot(settings: Any, store: Any) -> dict:
    """Privacy-safe runtime readiness. Never exposes secret values."""
    ai_enabled = bool(getattr(settings, "ai_enabled", True))
    ai_configured = bool(str(getattr(settings, "openai_api_key", "") or "").strip())
    supabase_secret = bool(str(getattr(settings, "supabase_service_role_key", "") or "").strip())
    supabase_url = bool(str(getattr(settings, "supabase_url", "") or "").strip())
    storage_class = type(store).__name__ if store is not None else "None"

    features = {
        "ai": ai_enabled and ai_configured,
        "persistent_memory_configured": supabase_secret and supabase_url,
        "live_knowledge": bool(getattr(settings, "live_knowledge_enabled", True)),
        "vod": bool(getattr(settings, "vod_enabled", True)),
        "voice": bool(getattr(settings, "voice_enabled", True)),
        "mini_app": True,
        "command_center": True,
    }
    required_ok = features["ai"]
    return {
        "ok": required_ok,
        "status": "ready" if required_ok else "degraded",
        "storage": {
            "configured_mode": str(getattr(settings, "storage_backend", "auto") or "auto")[:32],
            "active_adapter": storage_class[:64],
            "persistent_configured": features["persistent_memory_configured"],
            "resilient_fallback": "Resilient" in storage_class,
        },
        "features": features,
        "quality": quality_telemetry.snapshot(),
    }
