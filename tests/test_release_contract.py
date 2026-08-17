from __future__ import annotations

from types import SimpleNamespace

from app.observability.readiness import readiness_snapshot
from app.release import APP_VERSION, RELEASE_CONTRACT


class ReadyStore:
    def recovery_status(self):
        return {
            "primary_available": True,
            "outbox_pending": 0,
            "outbox_replayed": 3,
            "outbox_dropped": 0,
            "last_primary_error": "",
            "outbox_max": 500,
            "last_probe_ok": True,
            "last_probe_at": "2026-08-16T09:00:00+00:00",
            "probe_successes": 1,
            "probe_failures": 0,
        }

    def probe_primary(self):
        return True


class ReadyEntitlements:
    def readiness(self):
        return {"enabled": True, "configured": True, "last_success_at": None, "last_error": ""}


def _settings():
    return SimpleNamespace(
        ai_enabled=True,
        openai_api_key="configured-but-never-exposed",
        supabase_service_role_key="configured-but-never-exposed",
        supabase_url="https://example.supabase.co",
        storage_backend="auto",
        live_knowledge_enabled=True,
        vod_enabled=True,
        voice_enabled=True,
        voice_input_enabled=True,
        voice_transcription_model="gpt-4o-transcribe",
        voice_transcription_fallback_model="gpt-4o-mini-transcribe",
        voice_transcription_language="ru",
        voice_transcription_confidence_threshold=0.58,
        voice_input_max_duration_s=300,
        voice_follow_input_enabled=True,
        voice_provider="auto",
        voice_high_fidelity_enabled=True,
        voice_local_fallback_enabled=True,
        voice_openai_model="gpt-4o-mini-tts",
        voice_openai_voice="marin",
        voice_model_name="ru_RU-denis-medium",
        voice_opus_bitrate_kbps=72,
        voice_max_chars=3200,
        voice_duplex_max_chars=1800,
        usage_guard_enabled=True,
        telegram_max_update_bytes=256 * 1024,
        premium_link_enabled=True,
        telegram_aaa_console_enabled=True,
        telegram_live_drafts_enabled=True,
        webapp_live_stream_enabled=True,
        webapp_cinematic_ui_enabled=True,
        operator_intelligence_enabled=True,
        adaptive_mission_control_enabled=True,
        operator_context_bridge_enabled=True,
        mission_vod_evidence_fusion_enabled=True,
    )


def test_release_contract_is_explicit_and_readiness_exposes_natural_voice(monkeypatch):
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("PREMIUM_DEEP_HISTORY_ENABLED", "1")
    assert APP_VERSION == "33.0.0"
    assert RELEASE_CONTRACT == "bco-adaptive-exploration-budget-v33"
    snap = readiness_snapshot(
        _settings(),
        ReadyStore(),
        app_version=APP_VERSION,
        release_contract=RELEASE_CONTRACT,
        entitlement_service=ReadyEntitlements(),
    )
    assert snap["status"] == "ready"
    assert snap["release"] == {"version": "33.0.0", "contract": "bco-adaptive-exploration-budget-v33"}
    assert snap["features"]["persistent_memory_configured"] is True
    assert snap["features"]["telegram_aaa_command_console"] is True
    assert snap["features"]["telegram_live_intelligence_drafts"] is True
    assert snap["features"]["webapp_live_intelligence_stream"] is True
    assert snap["features"]["voice_input"] is True
    assert snap["features"]["voice_input_confidence_gate"] is True
    assert snap["features"]["voice_duplex_follow_input"] is True
    assert snap["features"]["voice_high_fidelity"] is True
    assert snap["features"]["voice_local_fallback"] is True
    assert snap["features"]["voice_natural_mastering"] is True
    assert snap["features"]["voice_selectable_profiles"] is True
    assert snap["features"]["operator_twin"] is True
    assert snap["features"]["adaptive_mission_control"] is True
    assert snap["features"]["operator_truth_calibration"] is True
    assert snap["features"]["operator_session_lifecycle"] is True
    assert snap["features"]["operator_context_bridge"] is True
    assert snap["features"]["operator_causal_intelligence"] is True
    assert snap["features"]["mission_vod_evidence_fusion"] is True
    assert snap["features"]["mission_vod_evidence_no_autocomplete"] is True
    assert snap["features"]["operator_longitudinal_intelligence"] is True
    assert snap["features"]["operator_longitudinal_contradiction_detection"] is True
    assert snap["features"]["operator_longitudinal_no_causal_claims"] is True
    assert snap["features"]["premium_deep_history"] is True
    assert snap["features"]["premium_deep_history_server_authoritative"] is True
    assert snap["features"]["premium_client_authority"] is False
    assert snap["features"]["premium_link_does_not_grant_entitlement"] is True
    assert snap["operator_intelligence"]["unknown_remains_unknown"] is True
    assert snap["operator_intelligence"]["adaptive_missions"] is True
    assert snap["operator_intelligence"]["context_bridge"] is True
    assert snap["operator_intelligence"]["shared_brain_context"] is True
    assert snap["operator_intelligence"]["context_schema"] == "bco_operator_context_v28"
    assert snap["operator_intelligence"]["mission_evidence_fusion"] is True
    assert snap["operator_intelligence"]["mission_evidence_source"] == "vision_sampled_frames"
    assert snap["operator_intelligence"]["mission_evidence_autocomplete"] is False
    assert snap["operator_intelligence"]["longitudinal_intelligence"] is True
    assert snap["operator_intelligence"]["longitudinal_schema"] == "bco_longitudinal_operator_v28"
    assert snap["operator_intelligence"]["longitudinal_minimum_cycles"] == 3
    assert snap["operator_intelligence"]["longitudinal_contradiction_detection"] is True
    assert snap["operator_intelligence"]["longitudinal_association_rule"] == "association_not_causation"
    assert snap["operator_intelligence"]["longitudinal_causal_claims"] is False
    assert snap["operator_intelligence"]["premium_deep_history"] is True
    assert snap["operator_intelligence"]["premium_deep_history_schema"] == "bco_premium_deep_history_v29"
    assert snap["operator_intelligence"]["premium_deep_history_max_cycles"] == 36
    assert snap["operator_intelligence"]["premium_deep_history_authority"] == "server_bco_premium"
    assert snap["operator_intelligence"]["premium_link_grants_entitlement"] is False
    assert snap["operator_intelligence"]["premium_client_authority"] is False
    assert snap["live_intelligence"]["final_message_authoritative"] is True
    assert snap["voice_runtime"]["input_configured"] is True
    assert snap["voice_runtime"]["transcription_model"] == "gpt-4o-transcribe"
    assert snap["voice_runtime"]["cloud_tts_configured"] is True
    assert snap["voice_runtime"]["default_voice"] == "marin"
    assert snap["voice_runtime"]["opus_bitrate_kbps"] == 72
    assert snap["storage"]["recovery"]["last_probe_ok"] is True
    rendered = repr(snap)
    assert "configured-but-never-exposed" not in rendered
    assert "example.supabase.co" not in rendered


def test_fastapi_version_uses_release_contract():
    from app.webhook import app

    assert app.version == APP_VERSION
