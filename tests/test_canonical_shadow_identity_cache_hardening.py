from __future__ import annotations

from uuid import UUID

import httpx

from app.observability.quality import QualityTelemetry
from app.services.storage.canonical_shadow import CanonicalReadShadowStore
from app.services.storage.supabase import SupabaseStore


OWNER = str(UUID("11111111-1111-1111-1111-111111111111"))


def _shadow(handler):
    primary = SupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
    )
    primary._client.close()
    primary._client = httpx.Client(transport=httpx.MockTransport(handler))
    return CanonicalReadShadowStore(
        primary,
        enabled=True,
        sample_rate=1.0,
        identity_cache_ttl_s=120,
        identity_negative_cache_ttl_s=30,
        telemetry=QualityTelemetry(),
    )


def test_resolved_owner_is_rechecked_on_every_shadow_read():
    candidate_calls = 0

    def handler(request: httpx.Request):
        nonlocal candidate_calls
        if request.url.path.endswith(
            "/rpc/black_crown_eligible_identity_candidates"
        ):
            candidate_calls += 1
            return httpx.Response(
                200,
                json=[
                    {
                        "black_crown_eligible_identity_candidates": [OWNER]
                    }
                ],
            )
        raise AssertionError(request.url)

    store = _shadow(handler)
    try:
        assert store._identity_candidates(42) == (OWNER,)
        assert store._identity_candidates(42) == (OWNER,)
        status = store.canonical_read_shadow_status()
    finally:
        store.close()

    assert candidate_calls == 2
    assert status["identity_cache_entries"] == 0
    assert status["negative_identity_cache_entries"] == 0
    assert status["resolved_identity_cache_enabled"] is False


def test_negative_cache_is_bounded_and_verified_identity_invalidates_it():
    candidate_calls = 0
    resolve_calls = 0

    def handler(request: httpx.Request):
        nonlocal candidate_calls, resolve_calls
        if request.url.path.endswith(
            "/rpc/black_crown_eligible_identity_candidates"
        ):
            candidate_calls += 1
            candidates = [] if candidate_calls == 1 else [OWNER]
            return httpx.Response(
                200,
                json=[
                    {
                        "black_crown_eligible_identity_candidates": candidates
                    }
                ],
            )
        if request.url.path.endswith(
            "/rpc/black_crown_resolve_telegram_identity"
        ):
            resolve_calls += 1
            return httpx.Response(
                200,
                json=[
                    {
                        "black_crown_user_id": OWNER,
                        "identity_status": "active",
                        "account_status": "active",
                    }
                ],
            )
        raise AssertionError(request.url)

    store = _shadow(handler)
    try:
        assert store._identity_candidates(42) == ()
        assert store._identity_candidates(42) == ()
        assert candidate_calls == 1
        assert store.canonical_read_shadow_status()[
            "negative_identity_cache_entries"
        ] == 1

        identity = store.resolve_telegram_identity(42)
        assert identity["black_crown_user_id"] == OWNER
        assert resolve_calls == 1
        assert store.canonical_read_shadow_status()[
            "negative_identity_cache_entries"
        ] == 0

        assert store._identity_candidates(42) == (OWNER,)
        assert candidate_calls == 2
        assert store.canonical_read_shadow_status()[
            "negative_identity_cache_entries"
        ] == 0
    finally:
        store.close()


def test_invalid_identity_response_does_not_manufacture_or_retain_owner():
    def handler(request: httpx.Request):
        if request.url.path.endswith(
            "/rpc/black_crown_resolve_telegram_identity"
        ):
            return httpx.Response(200, json=[])
        raise AssertionError(request.url)

    store = _shadow(handler)
    store._cache_identity(42, (), now=0.0)
    try:
        assert store.resolve_telegram_identity(42) == {}
        assert store.canonical_read_shadow_status()[
            "negative_identity_cache_entries"
        ] == 0
    finally:
        store.close()
