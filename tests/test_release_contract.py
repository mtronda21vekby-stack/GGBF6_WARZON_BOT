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
    )


def test_release_contract_is_explicit_and_readiness_exposes_natural_voice():
    assert APP_VERSION == "24.0.0"
    assert RELEASE_CONTRACT == "bco-voice-intelligence-v24"
    snap = readiness_snapshot(
        _settings(),
        ReadyStore(),
        app_version=APP_VERSION,
        release_contract=RELEASE_CONTRACT,
    )
    assert snap["status"] == "ready"
    assert snap["release"] == {"version": "24.0.0", "contract": "bco-voice-intelligence-v24"}
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
