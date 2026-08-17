from __future__ import annotations

from pathlib import Path
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
            "last_probe_at": "2026-08-17T09:00:00+00:00",
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
        voice_provider="auto",
        voice_high_fidelity_enabled=True,
        voice_local_fallback_enabled=True,
        voice_openai_model="gpt-4o-mini-tts",
        voice_openai_voice="cedar",
        voice_model_name="ru_RU-denis-medium",
        voice_opus_bitrate_kbps=48,
        usage_guard_enabled=True,
        telegram_max_update_bytes=256 * 1024,
        premium_link_enabled=True,
        telegram_aaa_console_enabled=True,
        telegram_live_drafts_enabled=True,
        webapp_live_stream_enabled=True,
        webapp_cinematic_ui_enabled=True,
        adaptive_mission_control_enabled=True,
    )


def test_v19_release_and_readiness_contract():
    assert APP_VERSION == "19.0.0"
    assert RELEASE_CONTRACT == "bco-adaptive-mission-control-v19"

    snap = readiness_snapshot(
        _settings(),
        ReadyStore(),
        app_version=APP_VERSION,
        release_contract=RELEASE_CONTRACT,
    )

    assert snap["status"] == "ready"
    assert snap["release"] == {
        "version": "19.0.0",
        "contract": "bco-adaptive-mission-control-v19",
    }
    assert snap["features"]["persistent_memory_configured"] is True
    assert snap["features"]["telegram_live_intelligence_drafts"] is True
    assert snap["features"]["webapp_live_intelligence_stream"] is True
    assert snap["features"]["webapp_cinematic_ui"] is True
    assert snap["features"]["adaptive_mission_control"] is True

    rendered = repr(snap)
    assert "configured-but-never-exposed" not in rendered
    assert "example.supabase.co" not in rendered


def test_v19_assets_and_boot_contract_are_present():
    root = Path(__file__).resolve().parents[1]
    boot = (root / "app/webapp/static/app.js").read_text(encoding="utf-8")
    runtime = (root / "app/webapp/static/command-center.js").read_text(encoding="utf-8")
    css = (root / "app/webapp/static/command-center.css").read_text(encoding="utf-8")

    assert "__BCO_COMMAND_CENTER_V19_LOADED__" in boot
    assert "/webapp/command-center.js" in boot
    assert "adaptive_mission_control" in boot
    assert "Adaptive Mission" in runtime or "ADAPTIVE MISSION" in runtime
    assert "mission" in runtime.casefold()
    assert "mission" in css.casefold()


def test_fastapi_version_uses_v19_release_contract():
    from app.webhook import app

    assert app.version == "19.0.0"
