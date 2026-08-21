from __future__ import annotations

import json
from uuid import UUID

import httpx

from app.observability.quality import QualityTelemetry
from app.services.storage.canonical_shadow import CanonicalReadShadowStore
from app.services.storage.supabase import SupabaseStore


OWNER = str(UUID("11111111-1111-1111-1111-111111111111"))
OTHER = str(UUID("22222222-2222-2222-2222-222222222222"))


def _store(handler, *, sample_rate: float = 1.0):
    primary = SupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
    )
    primary._client.close()
    primary._client = httpx.Client(transport=httpx.MockTransport(handler))
    telemetry = QualityTelemetry()
    return (
        CanonicalReadShadowStore(
            primary,
            enabled=True,
            sample_rate=sample_rate,
            telemetry=telemetry,
        ),
        telemetry,
    )


def _candidate_response(candidates):
    return httpx.Response(
        200,
        json=[{"black_crown_eligible_identity_candidates": candidates}],
    )


def test_shadow_match_returns_established_legacy_value():
    def handler(request: httpx.Request):
        path = request.url.path
        params = request.url.params
        if path.endswith("/rest/v1/bco_players") and params.get("chat_id"):
            return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])
        if path.endswith(
            "/rest/v1/rpc/black_crown_eligible_identity_candidates"
        ):
            body = json.loads(request.content.decode("utf-8"))
            assert body == {"p_provider": "telegram", "p_subject": "42"}
            return _candidate_response([OWNER])
        if path.endswith("/rest/v1/bco_players"):
            assert params["black_crown_user_id"] == f"eq.{OWNER}"
            assert "chat_id" not in params
            return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])
        raise AssertionError(f"unexpected request: {request.url}")

    store, telemetry = _store(handler)
    try:
        value = store.get_profile(42)
        status = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert value == {"game": "Warzone"}
    assert status["outcomes"] == {"match": 1}
    assert status["comparisons"] == 1
    assert status["returns_legacy"] is True
    assert status["canonical_primary_enabled"] is False


def test_shadow_mismatch_is_measured_but_never_returned():
    def handler(request: httpx.Request):
        path = request.url.path
        params = request.url.params
        if path.endswith("/rest/v1/bco_players") and params.get("chat_id"):
            return httpx.Response(200, json=[{"summary": "legacy"}])
        if path.endswith(
            "/rest/v1/rpc/black_crown_eligible_identity_candidates"
        ):
            return _candidate_response([OWNER])
        if path.endswith("/rest/v1/bco_players"):
            return httpx.Response(200, json=[{"summary": "different"}])
        raise AssertionError(f"unexpected request: {request.url}")

    store, telemetry = _store(handler)
    try:
        assert store.get_summary(42) == "legacy"
        outcomes = telemetry.snapshot()["canonical_read_shadow"]["outcomes"]
    finally:
        store.close()

    assert outcomes == {"mismatch": 1}


def test_shadow_identity_error_and_canonical_error_fail_to_legacy():
    calls = {"candidate": 0}

    def handler(request: httpx.Request):
        path = request.url.path
        params = request.url.params
        if path.endswith("/rest/v1/bco_players") and params.get("chat_id"):
            return httpx.Response(200, json=[{"derived": {"trend": "stable"}}])
        if path.endswith(
            "/rest/v1/rpc/black_crown_eligible_identity_candidates"
        ):
            calls["candidate"] += 1
            if calls["candidate"] == 1:
                return httpx.Response(503, json={"error": "unavailable"})
            return _candidate_response([OWNER])
        if path.endswith("/rest/v1/bco_players"):
            return httpx.Response(503, json={"error": "unavailable"})
        raise AssertionError(f"unexpected request: {request.url}")

    store, telemetry = _store(handler)
    store.identity_negative_cache_ttl_s = 0.001
    try:
        assert store.get_derived_intelligence(42) == {"trend": "stable"}
        store._identity_cache.clear()
        assert store.get_derived_intelligence(42) == {"trend": "stable"}
        outcomes = telemetry.snapshot()["canonical_read_shadow"]["outcomes"]
    finally:
        store.close()

    assert outcomes["identity_error"] == 1
    assert outcomes["canonical_error"] == 1


def test_unresolved_and_conflicting_identity_are_not_compared():
    candidates = [[], [OWNER, OTHER]]

    def handler(request: httpx.Request):
        if request.url.path.endswith("/rest/v1/bco_players"):
            return httpx.Response(200, json=[{"profile": {}}])
        if request.url.path.endswith(
            "/rest/v1/rpc/black_crown_eligible_identity_candidates"
        ):
            return _candidate_response(candidates.pop(0))
        raise AssertionError("canonical row query must be skipped")

    store, telemetry = _store(handler)
    try:
        assert store.get_profile(42) == {}
        store._identity_cache.clear()
        assert store.get_profile(42) == {}
        status = telemetry.snapshot()["canonical_read_shadow"]
    finally:
        store.close()

    assert status["outcomes"]["identity_unresolved"] == 1
    assert status["outcomes"]["identity_conflict"] == 1
    assert status["comparisons"] == 0


def test_ambiguous_canonical_profile_is_classified_and_legacy_wins():
    def handler(request: httpx.Request):
        path = request.url.path
        params = request.url.params
        if path.endswith("/rest/v1/bco_players") and params.get("chat_id"):
            return httpx.Response(200, json=[{"profile": {"game": "Warzone"}}])
        if path.endswith(
            "/rest/v1/rpc/black_crown_eligible_identity_candidates"
        ):
            return _candidate_response([OWNER])
        if path.endswith("/rest/v1/bco_players"):
            return httpx.Response(
                200,
                json=[
                    {"profile": {"game": "Warzone"}, "updated_at": "2026-08-21"},
                    {"profile": {"game": "BO7"}, "updated_at": "2026-08-20"},
                ],
            )
        raise AssertionError(f"unexpected request: {request.url}")

    store, telemetry = _store(handler)
    try:
        assert store.get_profile(42) == {"game": "Warzone"}
        outcomes = telemetry.snapshot()["canonical_read_shadow"]["outcomes"]
    finally:
        store.close()

    assert outcomes == {"canonical_ambiguous": 1}


def test_quality_snapshot_contains_no_identity_or_player_payload():
    telemetry = QualityTelemetry()
    telemetry.configure_canonical_read_shadow(enabled=True, sample_rate=0.1)
    telemetry.configure_canonical_read_control(
        database_enabled=True,
        reason="phase_2c_initial_enable",
        checked_at="2026-08-21T00:00:00Z",
    )
    telemetry.record_canonical_read(
        surface="profile",
        outcome="mismatch",
        latency_ms=12,
        legacy_items=2,
        canonical_items=2,
        compared=True,
    )

    encoded = json.dumps(telemetry.snapshot(), sort_keys=True)
    assert OWNER not in encoded
    assert "telegram_user_id" not in encoded
    assert "black_crown_user_id" not in encoded
    assert "message content" not in encoded
    assert '"read_authority": "legacy"' in encoded
    assert '"canonical_returned_to_callers": false' in encoded
