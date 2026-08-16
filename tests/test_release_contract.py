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
        usage_guard_enabled=True,
        telegram_max_update_bytes=256 * 1024,
    )


def test_release_contract_is_explicit_and_readiness_exposes_version_only():
    assert APP_VERSION == "12.0.0"
    assert RELEASE_CONTRACT == "bco-aaa-v12"
    snap = readiness_snapshot(
        _settings(),
        ReadyStore(),
        app_version=APP_VERSION,
        release_contract=RELEASE_CONTRACT,
    )
    assert snap["status"] == "ready"
    assert snap["release"] == {"version": "12.0.0", "contract": "bco-aaa-v12"}
    assert snap["features"]["persistent_memory_configured"] is True
    assert snap["storage"]["recovery"]["last_probe_ok"] is True
    rendered = repr(snap)
    assert "configured-but-never-exposed" not in rendered
    assert "example.supabase.co" not in rendered


def test_fastapi_version_uses_release_contract():
    from app.webhook import app

    assert app.version == APP_VERSION
