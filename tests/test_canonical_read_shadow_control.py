from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import httpx

from app.observability.quality import QualityTelemetry
from app.services.storage.canonical_shadow import CanonicalReadShadowStore
from app.services.storage.canonical_shadow_control import (
    CanonicalReadShadowControlStore,
)
from app.services.storage.factory import (
    PersistentResilientStore,
    PersistentSupabaseStore,
    build_store,
)
from app.services.storage.memory import InMemoryStore
from app.services.storage.supabase import SupabaseStore


OWNER = str(UUID("11111111-1111-1111-1111-111111111111"))


def _controlled_store(handler, *, local_enabled: bool = True):
    persistent = SupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
    )
    persistent._client.close()
    persistent._client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )
    telemetry = QualityTelemetry()
    shadow = CanonicalReadShadowStore(
        persistent,
        enabled=local_enabled,
        sample_rate=1.0,
        telemetry=telemetry,
    )
    return (
        CanonicalReadShadowControlStore(
            shadow,
            flag_ttl_s=600,
            telemetry=telemetry,
        ),
        telemetry,
    )


def test_database_flag_enabled_runs_shadow_and_caches_control_lookup():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        path = request.url.path
        params = request.url.params
        if path.endswith("/black_crown_ownership_runtime_flags"):
            return httpx.Response(
                200,
                json=[
                    {
                        "enabled": True,
                        "reason": "phase_2c_initial_enable",
                        "updated_at": "2026-08-21T00:00:00Z",
                    }
                ],
            )
        if path.endswith("/bco_players") and params.get("chat_id"):
            return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])
        if path.endswith("/rpc/black_crown_eligible_identity_candidates"):
            return httpx.Response(
                200,
                json=[{"black_crown_eligible_identity_candidates": [OWNER]}],
            )
        if path.endswith("/bco_players"):
            return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])
        raise AssertionError(f"unexpected request: {request.url}")

    store, telemetry = _controlled_store(handler)
    try:
        assert store.get_profile(42) == {"game": "Warzone"}
        assert store.get_profile(42) == {"game": "Warzone"}
        status = store.canonical_read_shadow_status()
        quality = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert calls.count(
        "/rest/v1/black_crown_ownership_runtime_flags"
    ) == 1
    assert status["database_enabled"] is True
    assert status["read_authority"] == "legacy"
    assert status["canonical_returned_to_callers"] is False
    assert quality["database_enabled"] is True
    assert quality["outcomes"]["match"] == 2


def test_database_flag_disabled_performs_only_established_read():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path.endswith(
            "/black_crown_ownership_runtime_flags"
        ):
            return httpx.Response(
                200,
                json=[{"enabled": False, "reason": "incident rollback"}],
            )
        if request.url.path.endswith("/bco_players"):
            return httpx.Response(200, json=[{"summary": "legacy"}])
        raise AssertionError("identity or canonical query must not run")

    store, telemetry = _controlled_store(handler)
    try:
        assert store.get_summary(42) == "legacy"
        quality = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert len(calls) == 2
    assert quality["database_enabled"] is False
    assert quality["outcomes"] == {"database_disabled": 1}


def test_control_lookup_error_fails_closed_without_breaking_read():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path.endswith(
            "/black_crown_ownership_runtime_flags"
        ):
            return httpx.Response(503, json={"error": "unavailable"})
        if request.url.path.endswith("/bco_players"):
            return httpx.Response(200, json=[{"summary": "legacy"}])
        raise AssertionError("identity or canonical query must not run")

    store, telemetry = _controlled_store(handler)
    try:
        assert store.get_summary(42) == "legacy"
        quality = telemetry.snapshot()["canonical_read_shadow"]
        status = store.canonical_read_shadow_status()
    finally:
        store.close()

    assert len(calls) == 2
    assert quality["control_errors"] == 1
    assert quality["outcomes"] == {"control_error": 1}
    assert status["database_enabled"] is False
    assert status["control_error"] == "HTTPStatusError"


def test_local_switch_skips_database_control_and_shadow_queries():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        assert request.url.path.endswith("/bco_players")
        return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])

    store, telemetry = _controlled_store(handler, local_enabled=False)
    try:
        assert store.get_profile(42) == {"game": "Warzone"}
        status = store.canonical_read_shadow_status()
        quality = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert calls == ["/rest/v1/bco_players"]
    assert status["database_enabled"] is None
    assert status["control_reason"] == "local_shadow_disabled"
    assert quality["events"] == 0


def test_factory_wires_concurrent_shadow_with_database_control(monkeypatch):
    monkeypatch.setenv("CANONICAL_READ_SHADOW_ENABLED", "0")
    monkeypatch.setenv("CANONICAL_READ_SHADOW_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("CANONICAL_READ_SHADOW_FLAG_TTL_S", "17")
    settings = SimpleNamespace(
        memory_max_turns=20,
        storage_backend="supabase",
        storage_timeout_s=8.0,
        storage_outbox_max=100,
        storage_replay_batch=10,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="server-secret",
        supabase_schema="public",
    )

    store = build_store(settings)
    try:
        assert isinstance(store, PersistentResilientStore)
        assert isinstance(store.primary, CanonicalReadShadowControlStore)
        assert isinstance(store.primary.shadow, CanonicalReadShadowStore)
        assert isinstance(store.primary.legacy, PersistentSupabaseStore)
        status = store.canonical_read_shadow_status()
    finally:
        store.close()

    assert status["enabled"] is False
    assert status["sample_rate"] == 0.25
    assert status["control_flag_ttl_s"] == 17.0
    assert status["returns_legacy"] is True


class IdentityPrimary:
    def resolve_telegram_identity(self, telegram_user_id: int):
        assert telegram_user_id == 42
        return {
            "black_crown_user_id": OWNER,
            "identity_status": "active",
            "account_status": "active",
        }


class IdentityFallback(InMemoryStore):
    pass


def test_resilient_store_exposes_server_identity_resolver():
    store = PersistentResilientStore(
        primary=IdentityPrimary(),
        fallback=IdentityFallback(),
    )
    assert store.resolve_telegram_identity(42) == {
        "black_crown_user_id": OWNER,
        "identity_status": "active",
        "account_status": "active",
    }


def test_memory_fallback_never_manufactures_canonical_identity():
    assert InMemoryStore().resolve_telegram_identity(42) == {}
