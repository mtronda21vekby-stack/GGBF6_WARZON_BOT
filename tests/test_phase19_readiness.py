from types import SimpleNamespace

from app.observability.readiness import readiness_snapshot


def test_readiness_reports_adaptive_mission_control():
    settings = SimpleNamespace(
        ai_enabled=True,
        openai_api_key="x",
        supabase_service_role_key="x",
        supabase_url="https://example.invalid",
        storage_backend="auto",
        live_knowledge_enabled=True,
        vod_enabled=True,
        voice_enabled=False,
        voice_provider="auto",
        voice_high_fidelity_enabled=False,
        voice_local_fallback_enabled=False,
        voice_openai_model="",
        voice_openai_voice="",
        voice_model_name="",
        voice_opus_bitrate_kbps=48,
        usage_guard_enabled=True,
        telegram_max_update_bytes=262144,
        telegram_aaa_console_enabled=True,
        telegram_live_drafts_enabled=True,
        webapp_live_stream_enabled=True,
        webapp_cinematic_ui_enabled=True,
        adaptive_mission_control_enabled=True,
    )
    snapshot = readiness_snapshot(settings, object(), app_version="19.0.0", release_contract="v19")
    assert snapshot["features"]["adaptive_mission_control"] is True
