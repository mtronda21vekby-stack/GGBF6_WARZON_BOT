from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.observability.readiness import readiness_snapshot
from app.release import (
    API_CONTRACT_VERSION,
    APP_VERSION,
    MINI_APP_RUNTIME,
    RELEASE_CONTRACT,
    TELEGRAM_AUTH_CONTRACT,
    VOICE_RUNTIME,
    runtime_build_metadata,
)


FULL_RENDER_SHA = "a" * 40
FULL_GITHUB_SHA = "b" * 40


class ReadyStore:
    def recovery_status(self):
        return {
            "primary_available": True,
            "outbox_pending": 0,
            "outbox_replayed": 0,
            "outbox_dropped": 0,
            "last_primary_error": "",
            "outbox_max": 500,
            "last_probe_ok": True,
            "last_probe_at": "2026-08-20T00:00:00+00:00",
            "probe_successes": 1,
            "probe_failures": 0,
        }

    def probe_primary(self):
        return True


class ReadyEntitlements:
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
        storage_backend="auto",
        usage_guard_enabled=True,
        telegram_max_update_bytes=256 * 1024,
        voice_enabled=True,
        voice_input_enabled=True,
        voice_high_fidelity_enabled=True,
        voice_local_fallback_enabled=True,
        voice_follow_input_enabled=True,
        voice_provider="auto",
        telegram_aaa_console_enabled=True,
        telegram_live_drafts_enabled=True,
        webapp_live_stream_enabled=True,
        webapp_cinematic_ui_enabled=True,
        operator_intelligence_enabled=True,
        adaptive_mission_control_enabled=True,
        operator_context_bridge_enabled=True,
        mission_vod_evidence_fusion_enabled=True,
    )


def test_runtime_build_metadata_prefers_exact_render_commit():
    metadata = runtime_build_metadata(
        {
            "RENDER_GIT_COMMIT": FULL_RENDER_SHA.upper(),
            "RENDER_GIT_BRANCH": "main",
            "GITHUB_SHA": FULL_GITHUB_SHA,
        }
    )

    assert metadata == {
        "schema": "bco-build-v1",
        "git_commit": FULL_RENDER_SHA,
        "git_commit_short": FULL_RENDER_SHA[:12],
        "source": "render",
        "branch": "main",
        "exact": True,
    }


def test_runtime_build_metadata_rejects_short_or_untrusted_values():
    metadata = runtime_build_metadata(
        {
            "RENDER_GIT_COMMIT": "deadbeef1234",
            "GITHUB_SHA": "not-a-git-sha",
            "SOURCE_COMMIT": "c" * 39,
            "RENDER_GIT_BRANCH": "main\nLEAK=secret",
            "OPENAI_API_KEY": "must-not-appear",
        }
    )

    assert metadata == {
        "schema": "bco-build-v1",
        "git_commit": "unknown",
        "git_commit_short": "unknown",
        "source": "unavailable",
        "branch": "unknown",
        "exact": False,
    }
    assert "must-not-appear" not in repr(metadata)


def test_readiness_exposes_separate_release_build_and_runtime_truth(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", FULL_RENDER_SHA)
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")

    snapshot = readiness_snapshot(
        _settings(),
        ReadyStore(),
        app_version=APP_VERSION,
        release_contract=RELEASE_CONTRACT,
        entitlement_service=ReadyEntitlements(),
    )

    # Backward-compatible product release object stays stable.
    assert snapshot["release"] == {
        "version": "44.0.0",
        "contract": "bco-aaa-war-room-alerts-v44",
    }
    assert snapshot["build"]["git_commit"] == FULL_RENDER_SHA
    assert snapshot["build"]["exact"] is True
    assert snapshot["contracts"] == {
        "api": API_CONTRACT_VERSION,
        "telegram_auth": TELEGRAM_AUTH_CONTRACT,
    }
    assert snapshot["runtimes"] == {
        "mini_app": {
            "id": MINI_APP_RUNTIME,
            "architecture": "layered_legacy",
            "consolidated": False,
        },
        "voice_frontend": {
            "id": VOICE_RUNTIME,
            "single_runtime": False,
        },
    }
    assert snapshot["identity"] == {
        "resolver_authority": "server",
        "telegram_ai_auth_required": True,
        "client_canonical_user_authority": False,
    }
    assert snapshot["entitlements"] == {
        "authority": "server_entitlement_service",
        "configured": True,
        "client_authority": False,
    }
    assert snapshot["storage"]["recovery"]["primary_available"] is True

    rendered = repr(snapshot)
    assert "never-expose-openai-secret" not in rendered
    assert "never-expose-supabase-secret" not in rendered
    assert "private-project.supabase.co" not in rendered


def test_render_workflow_requires_exact_build_and_protected_surface_smokes():
    workflow = Path(".github/workflows/render-production-deploy.yml").read_text(encoding="utf-8")

    for marker in (
        "statuses: write",
        "EXPECTED_SHA: ${{ github.sha }}",
        'build.get("git_commit") != expected_sha',
        'build.get("source") != "render"',
        'details.get("status") != "ready"',
        'recovery.get("primary_available") is not True',
        'recovery.get("last_probe_ok") is not True',
        'request_json("/webapp/health")',
        '"/webapp/app.js"',
        '"/webapp/bco.voice-v65.js"',
        'require_anonymous_denial("/webapp/api/ask"',
        'require_anonymous_denial("/webapp/api/ask/stream"',
        'require_anonymous_denial("/webapp/api/voice-speak"',
        '"/webapp/api/voice-transcribe"',
        '"/integrations/site/telegram/status"',
        '"context": "bco/render-production"',
    ):
        assert marker in workflow
