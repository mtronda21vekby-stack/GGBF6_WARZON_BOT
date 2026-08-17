# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any

from app.observability.quality import quality_telemetry


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


def readiness_snapshot(
    settings: Any,
    store: Any,
    *,
    app_version: str = "unknown",
    release_contract: str = "unknown",
    usage_guard: Any = None,
    replay_guard: Any = None,
    entitlement_service: Any = None,
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

    entitlement_snapshot: dict[str, Any] = {
        "enabled": False,
        "configured": False,
        "last_success_at": None,
        "last_error": "",
    }
    entitlement_readiness = getattr(entitlement_service, "readiness", None)
    if callable(entitlement_readiness):
        try:
            raw = dict(entitlement_readiness() or {})
            entitlement_snapshot = {
                "enabled": bool(raw.get("enabled", False)),
                "configured": bool(raw.get("configured", False)),
                "last_success_at": str(raw.get("last_success_at") or "")[:64] or None,
                "last_error": str(raw.get("last_error") or "")[:64],
            }
        except Exception:
            entitlement_snapshot = {
                "enabled": True,
                "configured": False,
                "last_success_at": None,
                "last_error": "readiness_unavailable",
            }

    voice_enabled = bool(getattr(settings, "voice_enabled", True))
    voice_input_enabled = bool(getattr(settings, "voice_input_enabled", True))
    voice_provider = str(getattr(settings, "voice_provider", "auto") or "auto").strip().casefold()
    voice_high_fidelity_enabled = bool(getattr(settings, "voice_high_fidelity_enabled", True))
    voice_local_fallback_enabled = bool(getattr(settings, "voice_local_fallback_enabled", True))
    voice_follow_input = bool(getattr(settings, "voice_follow_input_enabled", True))
    local_only = voice_provider in {"local", "offline", "piper_only", "piper-only", "local_only"}
    cloud_tts_configured = voice_enabled and voice_high_fidelity_enabled and ai_configured and not local_only
    voice_input_configured = voice_input_enabled and ai_configured
    voice_snapshot = {
        "enabled": voice_enabled,
        "input_enabled": voice_input_enabled,
        "input_configured": voice_input_configured,
        "transcription_model": str(getattr(settings, "voice_transcription_model", "gpt-4o-transcribe") or "")[:64],
        "transcription_fallback_model": str(getattr(settings, "voice_transcription_fallback_model", "gpt-4o-mini-transcribe") or "")[:64],
        "transcription_language": str(getattr(settings, "voice_transcription_language", "ru") or "")[:8],
        "transcription_confidence_threshold": max(0.0, min(1.0, float(getattr(settings, "voice_transcription_confidence_threshold", 0.58) or 0.58))),
        "input_max_duration_s": int(getattr(settings, "voice_input_max_duration_s", 300) or 300),
        "follow_input_enabled": voice_follow_input,
        "requested_provider": voice_provider[:32],
        "active_strategy": "cloud_first_local_fallback" if cloud_tts_configured else "local_only",
        "high_fidelity_enabled": voice_high_fidelity_enabled,
        "cloud_tts_configured": cloud_tts_configured,
        "local_fallback_enabled": voice_local_fallback_enabled,
        "cloud_model": str(getattr(settings, "voice_openai_model", "gpt-4o-mini-tts") or "")[:64],
        "default_voice": str(getattr(settings, "voice_openai_voice", "marin") or "")[:32],
        "available_ui_voices": ["marin", "coral", "shimmer", "cedar"],
        "local_model": str(getattr(settings, "voice_model_name", "ru_RU-denis-medium") or "")[:64],
        "opus_bitrate_kbps": int(getattr(settings, "voice_opus_bitrate_kbps", 72) or 72),
        "cloud_mastering": "natural_v3_transparent",
        "local_mastering": "piper_rescue_v2",
        "cloud_compression": False,
        "cloud_presence_boost": False,
        "output_sample_rate_hz": 48000,
        "speech_max_chars": int(getattr(settings, "voice_max_chars", 3200) or 3200),
        "duplex_max_chars": int(getattr(settings, "voice_duplex_max_chars", 1800) or 1800),
    }

    command_console_enabled = bool(getattr(settings, "telegram_aaa_console_enabled", True))
    telegram_live_drafts = bool(getattr(settings, "telegram_live_drafts_enabled", True))
    webapp_live_stream = bool(getattr(settings, "webapp_live_stream_enabled", True))
    webapp_cinematic = bool(getattr(settings, "webapp_cinematic_ui_enabled", True))
    operator_intelligence = bool(getattr(settings, "operator_intelligence_enabled", True))
    adaptive_missions = bool(getattr(settings, "adaptive_mission_control_enabled", True))
    operator_context_bridge = bool(getattr(settings, "operator_context_bridge_enabled", _env_on("OPERATOR_CONTEXT_BRIDGE_ENABLED")))
    mission_vod_fusion = bool(getattr(settings, "mission_vod_evidence_fusion_enabled", _env_on("MISSION_VOD_EVIDENCE_FUSION_ENABLED")))
    longitudinal = _env_on("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED")

    live_intelligence_snapshot = {
        "telegram_drafts": telegram_live_drafts,
        "telegram_transport": "rich_message_draft_with_text_fallback",
        "webapp_stream": webapp_live_stream,
        "webapp_transport": "ndjson",
        "cinematic_ui": webapp_cinematic,
        "final_message_authoritative": True,
    }
    operator_snapshot = {
        "enabled": operator_intelligence,
        "adaptive_missions": operator_intelligence and adaptive_missions,
        "context_bridge": operator_intelligence and operator_context_bridge,
        "shared_brain_context": operator_intelligence and operator_context_bridge,
        "context_schema": "bco_operator_context_v28",
        "mission_evidence_fusion": operator_intelligence and adaptive_missions and mission_vod_fusion,
        "mission_evidence_source": "vision_sampled_frames",
        "mission_evidence_autocomplete": False,
        "longitudinal_intelligence": operator_intelligence and longitudinal,
        "longitudinal_schema": "bco_longitudinal_operator_v28",
        "longitudinal_minimum_cycles": 3,
        "longitudinal_contradiction_detection": True,
        "longitudinal_association_rule": "association_not_causation",
        "longitudinal_causal_claims": False,
        "truth_model": "verified_fact|high_confidence_player_pattern|weak_pattern|hypothesis|unknown",
        "unknown_remains_unknown": True,
        "session_lifecycle": ["PRE_SESSION", "LIVE_OBJECTIVE", "POST_SESSION_REVIEW", "MEMORY_UPDATE", "NEXT_MISSION"],
        "persistence": "existing_progression_training_episode_store",
    }

    features = {
        "ai": ai_enabled and ai_configured,
        "persistent_memory_configured": supabase_secret and supabase_url,
        "live_knowledge": bool(getattr(settings, "live_knowledge_enabled", True)),
        "vod": bool(getattr(settings, "vod_enabled", True)),
        "voice": voice_enabled,
        "voice_input": voice_input_configured,
        "voice_input_confidence_gate": voice_input_configured,
        "voice_duplex_follow_input": voice_enabled and voice_follow_input,
        "voice_high_fidelity": cloud_tts_configured,
        "voice_local_fallback": voice_enabled and voice_local_fallback_enabled,
        "voice_natural_mastering": voice_enabled and cloud_tts_configured,
        "voice_selectable_profiles": voice_enabled,
        "mini_app": True,
        "command_center": True,
        "telegram_aaa_command_console": command_console_enabled,
        "telegram_inline_navigation": command_console_enabled,
        "telegram_rich_messages": command_console_enabled,
        "telegram_live_intelligence_drafts": telegram_live_drafts,
        "webapp_live_intelligence_stream": webapp_live_stream,
        "webapp_cinematic_ui": webapp_cinematic,
        "operator_twin": operator_intelligence,
        "adaptive_mission_control": operator_intelligence and adaptive_missions,
        "operator_truth_calibration": operator_intelligence,
        "operator_session_lifecycle": operator_intelligence and adaptive_missions,
        "operator_context_bridge": operator_intelligence and operator_context_bridge,
        "operator_causal_intelligence": operator_intelligence and operator_context_bridge,
        "mission_vod_evidence_fusion": operator_intelligence and adaptive_missions and mission_vod_fusion,
        "mission_vod_evidence_no_autocomplete": True,
        "operator_longitudinal_intelligence": operator_intelligence and longitudinal,
        "operator_longitudinal_contradiction_detection": True,
        "operator_longitudinal_no_causal_claims": True,
        "persistence_recovery": bool(recovery_fn),
        "storage_startup_probe": callable(getattr(store, "probe_primary", None)),
        "abuse_guard": bool(getattr(settings, "usage_guard_enabled", True)),
        "telegram_replay_dedupe": replay_guard is not None,
        "premium_account_link": entitlement_snapshot["enabled"] and entitlement_snapshot["configured"],
        "premium_entitlement_authority": entitlement_snapshot["configured"],
    }
    primary_degraded = bool(recovery) and recovery.get("primary_available") is False
    probe_failed = bool(recovery) and recovery.get("last_probe_ok") is False
    required_ok = features["ai"]
    status = "degraded" if (not required_ok or primary_degraded or probe_failed) else "ready"
    return {
        "ok": required_ok,
        "status": status,
        "release": {"version": str(app_version or "unknown")[:32], "contract": str(release_contract or "unknown")[:64]},
        "storage": {
            "configured_mode": str(getattr(settings, "storage_backend", "auto") or "auto")[:32],
            "active_adapter": storage_class[:64],
            "persistent_configured": features["persistent_memory_configured"],
            "resilient_fallback": "Resilient" in storage_class,
            "recovery": recovery,
        },
        "voice_runtime": voice_snapshot,
        "live_intelligence": live_intelligence_snapshot,
        "operator_intelligence": operator_snapshot,
        "premium_link": entitlement_snapshot,
        "features": features,
        "abuse_guard": {
            "usage": guard_snapshot,
            "telegram_replay": replay_snapshot,
            "telegram_max_update_bytes": int(getattr(settings, "telegram_max_update_bytes", 0) or 0),
        },
        "quality": quality_telemetry.snapshot(),
    }
