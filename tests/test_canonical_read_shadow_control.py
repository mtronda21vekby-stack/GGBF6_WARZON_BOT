from __future__ import annotations

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


def _status_response(
    *,
    enabled: bool = True,
    dual_write_enabled: bool = True,
    conflict_count: int = 0,
    merge_pending_count: int = 0,
    coverage_ready: bool = True,
    promotion_ready: bool | None = None,
    blockers: list[str] | None = None,
    schema: str = "bco-canonical-read-shadow-v2",
    raw_reason: str = "never expose this operator note",
):
    if promotion_ready is None:
        promotion_ready = bool(
            enabled
            and dual_write_enabled
            and conflict_count == 0
            and merge_pending_count == 0
            and coverage_ready
        )
    if blockers is None:
        blockers = []
        if not enabled:
            blockers.append("shadow_disabled")
        if not dual_write_enabled:
            blockers.append("dual_write_disabled")
        if conflict_count:
            blockers.append("identity_conflict")
        if merge_pending_count:
            blockers.append("merge_pending")
        if not coverage_ready:
            blockers.append("coverage_incomplete")
    return httpx.Response(
        200,
        json=[
            {
                "schema_version": schema,
                "shadow_read_enabled": enabled,
                "shadow_read_reason": raw_reason,
                "shadow_read_updated_at": "2026-08-21T00:00:00Z",
                "dual_write_enabled": dual_write_enabled,
                "resolved_count": 3,
                "unresolved_count": 2,
                "conflict_count": conflict_count,
                "merge_pending_count": merge_pending_count,
                "shadow_surface_coverage_ready": coverage_ready,
                "promotion_ready": promotion_ready,
                "promotion_blockers": blockers,
            }
        ],
    )


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


def test_database_status_enabled_runs_shadow_and_caches_control_only():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        path = request.url.path
        params = request.url.params
        if path.endswith("/black_crown_canonical_read_runtime_status"):
            assert "shadow_read_reason" not in str(params.get("select") or "")
            return _status_response()
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
        "/rest/v1/black_crown_canonical_read_runtime_status"
    ) == 1
    # Control is cached, but a successful owner is resolved on every shadow read.
    assert calls.count(
        "/rest/v1/rpc/black_crown_eligible_identity_candidates"
    ) == 2
    assert status["database_enabled"] is True
    assert status["database_flag_enabled"] is True
    assert status["control_reason"] == "database_enabled"
    assert status["promotion_ready"] is True
    assert status["promotion_blockers"] == []
    assert status["read_authority"] == "legacy"
    assert status["canonical_returned_to_callers"] is False
    assert status["resolved_identity_cache_enabled"] is False
    assert quality["database_enabled"] is True
    assert quality["promotion_ready"] is True
    assert quality["outcomes"]["match"] == 2
    assert "never expose this operator note" not in repr(status)
    assert "never expose this operator note" not in repr(quality)


def test_database_flag_disabled_performs_only_established_read():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path.endswith(
            "/black_crown_canonical_read_runtime_status"
        ):
            return _status_response(enabled=False)
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
    assert quality["promotion_ready"] is False
    assert quality["promotion_blockers"] == ["shadow_disabled"]
    assert quality["outcomes"] == {"database_disabled": 1}


def test_control_lookup_error_fails_closed_without_breaking_read():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path.endswith(
            "/black_crown_canonical_read_runtime_status"
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
    assert quality["promotion_blockers"] == ["control_error"]
    assert quality["outcomes"] == {"control_error": 1}
    assert status["database_enabled"] is False
    assert status["control_error"] == "HTTPStatusError"


def test_mapping_conflict_disables_all_shadow_queries():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path.endswith(
            "/black_crown_canonical_read_runtime_status"
        ):
            return _status_response(
                conflict_count=1,
                promotion_ready=False,
                blockers=["identity_conflict"],
            )
        if request.url.path.endswith("/bco_players"):
            return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])
        raise AssertionError("identity/canonical shadow query must be blocked")

    store, telemetry = _controlled_store(handler)
    try:
        assert store.get_profile(42) == {"game": "Warzone"}
        status = store.canonical_read_shadow_status()
        quality = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert calls == [
        "/rest/v1/black_crown_canonical_read_runtime_status",
        "/rest/v1/bco_players",
    ]
    assert status["control_state"] == "mapping_conflict"
    assert status["identity_conflicts"] == 1
    assert status["promotion_ready"] is False
    assert quality["outcomes"] == {"mapping_conflict": 1}


def test_incomplete_coverage_keeps_shadow_active_but_blocks_promotion():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        path = request.url.path
        params = request.url.params
        if path.endswith("/black_crown_canonical_read_runtime_status"):
            return _status_response(
                coverage_ready=False,
                promotion_ready=False,
                blockers=["coverage_incomplete"],
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
        raise AssertionError(request.url)

    store, telemetry = _controlled_store(handler)
    try:
        assert store.get_profile(42) == {"game": "Warzone"}
        status = store.canonical_read_shadow_status()
        quality = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert calls.count(
        "/rest/v1/rpc/black_crown_eligible_identity_candidates"
    ) == 1
    assert status["database_enabled"] is True
    assert status["coverage_ready"] is False
    assert status["promotion_ready"] is False
    assert status["promotion_blockers"] == ["coverage_incomplete"]
    assert quality["promotion_blockers"] == ["coverage_incomplete"]
    assert quality["outcomes"] == {"match": 1}


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
    assert status["promotion_blockers"] == ["shadow_disabled"]
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
