from __future__ import annotations

from types import SimpleNamespace

from app.observability.readiness import readiness_snapshot


OWNER = "11111111-1111-1111-1111-111111111111"
RAW_SUBJECT = "telegram-subject-must-not-leak"


class LifecycleReadyStore:
    def recovery_status(self):
        return {
            "primary_available": True,
            "outbox_pending": 0,
            "outbox_replayed": 0,
            "outbox_dropped": 0,
            "last_primary_error": "",
            "outbox_max": 500,
            "last_probe_ok": True,
            "last_probe_at": "2026-08-21T01:00:00+00:00",
            "probe_successes": 1,
            "probe_failures": 0,
        }

    def probe_primary(self):
        return True

    def canonical_lifecycle_status(self):
        return {
            "schema": "bco-canonical-lifecycle-v1",
            "enabled": False,
            "mode": "legacy_subject",
            "reason": "phase_2d_staged_disabled",
            "updated_at": "2026-08-21T01:00:00+00:00",
            "dual_write_enabled": True,
            "shadow_read_enabled": True,
            "resolved_mappings": 3,
            "unresolved_mappings": 2,
            "conflict_mappings": 0,
            "merge_pending_mappings": 0,
            "legacy_fallback_available": True,
            "account_deletion_enabled": False,
            "identity_deletion_enabled": False,
            "entitlement_deletion_enabled": False,
            "black_crown_user_id": OWNER,
            "provider_subject": RAW_SUBJECT,
            "secret": "never-expose-storage-secret",
        }


class EntitlementsReady:
    def readiness(self):
        return {
            "enabled": True,
            "configured": True,
            "last_success_at": None,
            "last_error": "",
        }


def _settings():
    return SimpleNamespace(
        ai_enabled=True,
        openai_api_key="never-expose-openai-secret",
        supabase_service_role_key="never-expose-supabase-secret",
        supabase_url="https://private-project.supabase.co",
        storage_backend="supabase",
        usage_guard_enabled=True,
        telegram_max_update_bytes=256 * 1024,
        voice_enabled=False,
        voice_input_enabled=False,
        voice_provider="local",
        voice_high_fidelity_enabled=False,
        voice_local_fallback_enabled=True,
        voice_follow_input_enabled=False,
        telegram_aaa_console_enabled=True,
        telegram_live_drafts_enabled=True,
        webapp_live_stream_enabled=True,
        webapp_cinematic_ui_enabled=True,
        operator_intelligence_enabled=True,
        adaptive_mission_control_enabled=True,
        operator_context_bridge_enabled=True,
        mission_vod_evidence_fusion_enabled=True,
        live_knowledge_enabled=True,
        vod_enabled=True,
    )


def test_health_details_exposes_staged_lifecycle_without_identity_material():
    snapshot = readiness_snapshot(
        _settings(),
        LifecycleReadyStore(),
        app_version="44.0.0",
        release_contract="bco-aaa-war-room-alerts-v44",
        entitlement_service=EntitlementsReady(),
    )

    assert snapshot["storage"]["canonical_lifecycle"] == {
        "schema": "bco-canonical-lifecycle-v1",
        "enabled": False,
        "mode": "legacy_subject",
        "reason": "phase_2d_staged_disabled",
        "updated_at": "2026-08-21T01:00:00+00:00",
        "dual_write_enabled": True,
        "shadow_read_enabled": True,
        "resolved_mappings": 3,
        "unresolved_mappings": 2,
        "conflict_mappings": 0,
        "merge_pending_mappings": 0,
        "legacy_fallback_available": True,
        "account_deletion_enabled": False,
        "identity_deletion_enabled": False,
        "entitlement_deletion_enabled": False,
    }
    assert snapshot["features"]["canonical_lifecycle_contract"] is True
    assert snapshot["features"]["canonical_lifecycle_enabled"] is False
    assert snapshot["features"]["canonical_lifecycle_legacy_fallback"] is True
    assert snapshot["features"]["canonical_lifecycle_preserves_account"] is True
    assert snapshot["features"]["canonical_lifecycle_preserves_identity"] is True
    assert snapshot["features"]["canonical_lifecycle_preserves_entitlement"] is True

    rendered = repr(snapshot)
    for forbidden in (
        OWNER,
        RAW_SUBJECT,
        "never-expose-storage-secret",
        "never-expose-openai-secret",
        "never-expose-supabase-secret",
        "private-project.supabase.co",
    ):
        assert forbidden not in rendered


def test_health_details_fails_safe_when_lifecycle_status_is_unavailable():
    class FailingStore(LifecycleReadyStore):
        def canonical_lifecycle_status(self):
            raise RuntimeError("raw internal lifecycle failure")

    snapshot = readiness_snapshot(_settings(), FailingStore())
    lifecycle = snapshot["storage"]["canonical_lifecycle"]

    assert lifecycle["enabled"] is False
    assert lifecycle["mode"] == "legacy_subject"
    assert lifecycle["legacy_fallback_available"] is True
    assert lifecycle["account_deletion_enabled"] is False
    assert lifecycle["identity_deletion_enabled"] is False
    assert lifecycle["entitlement_deletion_enabled"] is False
    assert lifecycle["reason"] == "readiness_unavailable"
    assert lifecycle["control_error"] == "RuntimeError"
    assert "raw internal lifecycle failure" not in repr(snapshot)
