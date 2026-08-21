from __future__ import annotations

import json
from collections import Counter

import httpx

from app.observability.readiness import readiness_snapshot
from app.services.storage.factory import PersistentSupabaseStore


OWNER = "11111111-1111-1111-1111-111111111111"


def _store(handler, **kwargs) -> PersistentSupabaseStore:
    store = PersistentSupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
        canonical_read_flag_cache_ttl_s=60,
        canonical_read_identity_cache_ttl_s=60,
        **kwargs,
    )
    old = store._client
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    old.close()
    return store


def _flag_response(request: httpx.Request, enabled: bool = True) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json=[{
            "enabled": enabled,
            "reason": "test_enabled" if enabled else "test_disabled",
            "updated_at": "2026-08-21T01:00:00Z",
        }],
    )


def _owner_response(
    request: httpx.Request,
    *,
    state: str = "resolved",
    owner: str | None = OWNER,
    candidate_count: int = 1,
) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json=[{
            "resolution_state": state,
            "black_crown_user_id": owner,
            "candidate_count": candidate_count,
            "schema_version": "bco-canonical-read-v1",
        }],
    )


def test_canonical_message_hit_uses_server_resolved_owner_only():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request)
        if request.url.path.endswith("/rpc/black_crown_resolve_read_owner"):
            body = json.loads(request.content.decode("utf-8"))
            assert body == {"p_provider": "telegram", "p_subject": "42"}
            return _owner_response(request)
        if request.url.path.endswith("/bco_messages"):
            assert request.url.params.get("black_crown_user_id") == f"eq.{OWNER}"
            assert request.url.params.get("chat_id") is None
            return httpx.Response(
                200,
                request=request,
                json=[{"role": "assistant", "content": "canonical"}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.get(42) == [{"role": "assistant", "content": "canonical"}]
        snapshot = store._canonical_reads.snapshot(refresh_flag=False)
    finally:
        store.close()

    assert snapshot["canonical_hits"] == 1
    assert snapshot["legacy_fallbacks"] == 0
    assert OWNER not in repr(snapshot)
    assert sum(request.url.path.endswith("/bco_messages") for request in seen) == 1


def test_disabled_database_flag_skips_identity_lookup_and_uses_legacy_profile():
    calls = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        calls[request.url.path] += 1
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request, enabled=False)
        if request.url.path.endswith("/bco_players"):
            assert request.url.params.get("chat_id") == "eq.7"
            assert request.url.params.get("black_crown_user_id") is None
            return httpx.Response(
                200,
                request=request,
                json=[{"profile": {"game": "Warzone"}}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.get_profile(7) == {"game": "Warzone"}
        snapshot = store._canonical_reads.snapshot(refresh_flag=False)
    finally:
        store.close()

    assert not any(path.endswith("/rpc/black_crown_resolve_read_owner") for path in calls)
    assert snapshot["mode"] == "legacy"
    assert snapshot["legacy_fallbacks"] == 1


def test_unresolved_identity_falls_back_without_querying_another_owner():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request)
        if request.url.path.endswith("/rpc/black_crown_resolve_read_owner"):
            return _owner_response(
                request,
                state="unresolved",
                owner=None,
                candidate_count=0,
            )
        if request.url.path.endswith("/bco_episodes"):
            assert request.url.params.get("chat_id") == "eq.8"
            assert request.url.params.get("black_crown_user_id") is None
            return httpx.Response(
                200,
                request=request,
                json=[{"kind": "legacy", "data": {}, "created_at": "now"}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.list_episodes(8)[0]["kind"] == "legacy"
        snapshot = store._canonical_reads.snapshot(refresh_flag=False)
    finally:
        store.close()

    assert snapshot["identity_unresolved_fallbacks"] == 1
    assert all(OWNER not in str(request.url) for request in seen)


def test_conflicting_identity_falls_back_to_exact_legacy_subject():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request)
        if request.url.path.endswith("/rpc/black_crown_resolve_read_owner"):
            return _owner_response(
                request,
                state="conflict",
                owner=None,
                candidate_count=2,
            )
        if request.url.path.endswith("/bco_progression_events"):
            assert request.url.params.get("chat_id") == "eq.9"
            return httpx.Response(
                200,
                request=request,
                json=[{"data": {"xp": 1}, "created_at": "now"}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.list_progression_events(9)[0]["xp"] == 1
        snapshot = store._canonical_reads.snapshot(refresh_flag=False)
    finally:
        store.close()

    assert snapshot["identity_conflict_fallbacks"] == 1


def test_ambiguous_singleton_never_silently_merges_profiles():
    profile_queries = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal profile_queries
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request)
        if request.url.path.endswith("/rpc/black_crown_resolve_read_owner"):
            return _owner_response(request)
        if request.url.path.endswith("/bco_players"):
            profile_queries += 1
            if request.url.params.get("black_crown_user_id"):
                assert request.url.params.get("limit") == "2"
                return httpx.Response(
                    200,
                    request=request,
                    json=[
                        {"profile": {"game": "A"}},
                        {"profile": {"game": "B"}},
                    ],
                )
            assert request.url.params.get("chat_id") == "eq.10"
            return httpx.Response(
                200,
                request=request,
                json=[{"profile": {"game": "Legacy"}}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.get_profile(10) == {"game": "Legacy"}
        snapshot = store._canonical_reads.snapshot(refresh_flag=False)
    finally:
        store.close()

    assert profile_queries == 2
    assert snapshot["canonical_ambiguous"] == 1
    assert snapshot["legacy_fallbacks"] == 1


def test_canonical_query_failure_is_fail_closed_to_legacy():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request)
        if request.url.path.endswith("/rpc/black_crown_resolve_read_owner"):
            return _owner_response(request)
        if request.url.path.endswith("/bco_training_sessions"):
            if request.url.params.get("black_crown_user_id"):
                return httpx.Response(503, request=request, json={"error": "down"})
            return httpx.Response(
                200,
                request=request,
                json=[{"data": {"mission": "legacy"}, "created_at": "now"}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.list_training_sessions(11)[0]["mission"] == "legacy"
        snapshot = store._canonical_reads.snapshot(refresh_flag=False)
    finally:
        store.close()

    assert snapshot["canonical_query_errors"] == 1
    assert snapshot["legacy_fallbacks"] == 1


def test_server_identity_resolution_primes_owner_cache():
    calls = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        calls[request.url.path] += 1
        if request.url.path.endswith("/rpc/black_crown_resolve_telegram_identity"):
            return httpx.Response(
                200,
                request=request,
                json=[{
                    "black_crown_user_id": OWNER,
                    "identity_status": "active",
                    "account_status": "active",
                }],
            )
        if request.url.path.endswith("/black_crown_ownership_runtime_flags"):
            return _flag_response(request)
        if request.url.path.endswith("/bco_players"):
            assert request.url.params.get("black_crown_user_id") == f"eq.{OWNER}"
            return httpx.Response(
                200,
                request=request,
                json=[{"summary": "shared"}],
            )
        raise AssertionError(request.url)

    store = _store(handler)
    try:
        assert store.resolve_telegram_identity(12)["black_crown_user_id"] == OWNER
        assert store.get_summary(12) == "shared"
    finally:
        store.close()

    assert not any(path.endswith("/rpc/black_crown_resolve_read_owner") for path in calls)


def test_readiness_exposes_privacy_safe_canonical_read_state():
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
                "last_probe_at": "now",
                "probe_successes": 1,
                "probe_failures": 0,
            }

        def probe_primary(self):
            return True

        def canonical_read_status(self):
            return {
                "schema_version": "bco-canonical-read-v1",
                "capability_enabled": True,
                "database_flag_enabled": True,
                "mode": "canonical_first",
                "flag_reason": "enabled",
                "canonical_hits": 3,
                "legacy_fallbacks": 1,
                "by_table": {"bco_messages": {"canonical_hit": 3}},
                "debug_owner": OWNER,
            }

    class Settings:
        ai_enabled = True
        openai_api_key = "configured-secret"
        supabase_service_role_key = "configured-secret"
        supabase_url = "https://example.supabase.co"
        storage_backend = "supabase"
        live_knowledge_enabled = True
        vod_enabled = True
        voice_enabled = False
        voice_input_enabled = False
        usage_guard_enabled = True
        telegram_max_update_bytes = 1024

    snapshot = readiness_snapshot(Settings(), ReadyStore())
    canonical = snapshot["storage"]["canonical_read"]
    assert canonical["mode"] == "canonical_first"
    assert canonical["canonical_hits"] == 3
    assert snapshot["features"]["canonical_owner_first_reads"] is True
    assert snapshot["identity"]["product_owner_key"] == "black_crown_user_id"
    assert OWNER not in repr(snapshot)
    assert "configured-secret" not in repr(snapshot)
