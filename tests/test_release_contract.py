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
    monkeypatch.setenv("EVIDENCE_FRESHNESS_ENABLED", "1")
    monkeypatch.setenv("REGIME_CHANGE_DETECTION_ENABLED", "1")
    monkeypatch.setenv("MISSION_ORCHESTRATOR_ENABLED", "1")
    assert APP_VERSION == "36.0.0"
    assert RELEASE_CONTRACT == "bco-mission-orchestrator-v36"
    snap = readiness_snapshot(
        _settings(),
        ReadyStore(),
        app_version=APP_VERSION,
        release_contract=RELEASE_CONTRACT,
        entitlement_service=ReadyEntitlements(),
    )
    assert snap["status"] == "ready"
    assert snap["release"] == {"version": "36.0.0", "contract": "bco-mission-orchestrator-v36"}

    features = snap["features"]
    for key in (
        "persistent_memory_configured",
        "telegram_aaa_command_console",
        "telegram_live_intelligence_drafts",
        "webapp_live_intelligence_stream",
        "voice_input",
        "voice_input_confidence_gate",
        "voice_duplex_follow_input",
        "voice_high_fidelity",
        "voice_local_fallback",
        "voice_natural_mastering",
        "voice_selectable_profiles",
        "operator_twin",
        "adaptive_mission_control",
        "operator_truth_calibration",
        "operator_session_lifecycle",
        "operator_context_bridge",
        "operator_causal_intelligence",
        "mission_vod_evidence_fusion",
        "mission_vod_evidence_no_autocomplete",
        "operator_longitudinal_intelligence",
        "operator_longitudinal_contradiction_detection",
        "operator_longitudinal_no_causal_claims",
        "premium_deep_history",
        "premium_deep_history_server_authoritative",
        "premium_link_does_not_grant_entitlement",
        "operator_evidence_freshness",
        "operator_stale_evidence_not_false",
        "operator_freshness_no_causal_claims",
        "operator_regime_change_detection",
        "operator_regime_requires_sustained_windows",
        "operator_regime_one_session_not_enough",
        "operator_regime_no_causal_claims",
        "operator_regime_external_meta_not_inferred",
        "operator_mission_orchestrator",
        "operator_mission_stage_explicit_only",
        "operator_vod_cannot_advance_stage",
        "operator_stale_history_cannot_skip_recalibration",
        "operator_mission_stage_not_player_fact",
        "operator_mission_stage_no_causal_claims",
    ):
        assert features[key] is True
    assert features["premium_client_authority"] is False

    op = snap["operator_intelligence"]
    assert op["unknown_remains_unknown"] is True
    assert op["context_schema"] == "bco_operator_context_v28"
    assert op["mission_evidence_source"] == "vision_sampled_frames"
    assert op["mission_evidence_autocomplete"] is False
    assert op["longitudinal_schema"] == "bco_longitudinal_operator_v28"
    assert op["longitudinal_minimum_cycles"] == 3
    assert op["longitudinal_contradiction_detection"] is True
    assert op["longitudinal_association_rule"] == "association_not_causation"
    assert op["longitudinal_causal_claims"] is False
    assert op["premium_deep_history_schema"] == "bco_premium_deep_history_v29"
    assert op["premium_deep_history_max_cycles"] == 36
    assert op["premium_deep_history_authority"] == "server_bco_premium"
    assert op["premium_link_grants_entitlement"] is False
    assert op["premium_client_authority"] is False
    assert op["evidence_freshness_schema"] == "bco_evidence_freshness_v34"
    assert op["evidence_freshness_authority"] == "server_persisted_evidence_timestamps_only"
    assert op["evidence_freshness_fresh_max_days"] == 7
    assert op["evidence_freshness_aging_max_days"] == 21
    assert op["stale_evidence_is_false"] is False
    assert op["freshness_causal_claims"] is False
    assert op["regime_change_schema"] == "bco_player_regime_change_v35"
    assert op["regime_change_authority"] == "server_explicit_outcome_windows_only"
    assert op["regime_minimum_candidate_cycles"] == 6
    assert op["regime_minimum_confirmed_cycles"] == 9
    assert op["regime_window_size"] == 3
    assert op["regime_one_session_can_change"] is False
    assert op["regime_shift_identifies_cause"] is False
    assert op["regime_external_meta_inferred"] is False
    assert op["regime_causal_claims"] is False

    assert op["mission_orchestrator"] is True
    assert op["mission_orchestrator_schema"] == "bco_mission_orchestrator_v36"
    assert op["mission_orchestrator_stages"] == [
        "CALIBRATION", "CORRECTION", "VALIDATION", "STRESS_TEST", "MAINTENANCE"
    ]
    assert op["mission_orchestrator_transition_authority"] == "explicit_operator_report_only"
    assert op["mission_orchestrator_vod_transition_authority"] is False
    assert op["mission_orchestrator_current_horizon_max_days"] == 21
    assert op["mission_orchestrator_reported_without_verdict_advances"] is False
    assert op["mission_orchestrator_stage_is_player_fact"] is False
    assert op["mission_orchestrator_stage_transition_proves_cause"] is False

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
