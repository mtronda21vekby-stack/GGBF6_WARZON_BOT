from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx

from app.observability.quality import QualityTelemetry
from app.services.storage.canonical_shadow import CanonicalReadShadowStore
from app.services.storage.factory import PersistentResilientStore, build_store


OWNER_ID = "11111111-1111-1111-1111-111111111111"


class FakePrimary:
    memory_max_turns = 20

    def __init__(
        self,
        *,
        candidates: Any = None,
        canonical_profile_rows: list[dict] | None = None,
        canonical_error: bool = False,
    ) -> None:
        self.candidates = [OWNER_ID] if candidates is None else candidates
        self.canonical_profile_rows = (
            [{"profile": {"game": "Warzone"}, "updated_at": "2026-08-20"}]
            if canonical_profile_rows is None
            else canonical_profile_rows
        )
        self.canonical_error = canonical_error
        self.calls: list[tuple[str, str]] = []

    def get_profile(self, chat_id: int) -> dict:
        assert chat_id == 42
        return {"game": "Warzone", "sensitive": "legacy-secret-value"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params=None,
        json=None,
        extra_headers=None,
    ) -> httpx.Response:
        self.calls.append((method, path))
        request = httpx.Request(method, f"https://example.test/{path}")
        if path.startswith("rpc/"):
            return httpx.Response(
                200,
                request=request,
                json=self.candidates,
            )
        if self.canonical_error:
            raise RuntimeError("canonical shadow unavailable")
        return httpx.Response(
            200,
            request=request,
            json=self.canonical_profile_rows,
        )

    @staticmethod
    def _rows(response: httpx.Response) -> list[dict]:
        data = response.json()
        return data if isinstance(data, list) else []

    def close(self) -> None:
        return None


def test_shadow_read_returns_legacy_and_records_content_free_parity():
    telemetry = QualityTelemetry()
    primary = FakePrimary(
        canonical_profile_rows=[
            {
                "profile": {
                    "game": "Warzone",
                    "sensitive": "legacy-secret-value",
                },
                "updated_at": "2026-08-20",
            }
        ]
    )
    store = CanonicalReadShadowStore(primary, telemetry=telemetry)

    result = store.get_profile(42)

    assert result == {
        "game": "Warzone",
        "sensitive": "legacy-secret-value",
    }
    snapshot = telemetry.snapshot()["canonical_read_shadow"]
    assert snapshot["returns_legacy"] is True
    assert snapshot["canonical_primary_enabled"] is False
    assert snapshot["comparisons"] == 1
    assert snapshot["outcomes"] == {"match": 1}
    rendered = repr(snapshot)
    assert "legacy-secret-value" not in rendered
    assert OWNER_ID not in rendered


def test_mismatch_never_replaces_live_legacy_value():
    telemetry = QualityTelemetry()
    primary = FakePrimary(
        canonical_profile_rows=[
            {
                "profile": {"game": "Black Ops 7"},
                "updated_at": "2026-08-20",
            }
        ]
    )
    store = CanonicalReadShadowStore(primary, telemetry=telemetry)

    result = store.get_profile(42)

    assert result["game"] == "Warzone"
    snapshot = telemetry.snapshot()["canonical_read_shadow"]
    assert snapshot["outcomes"] == {"mismatch": 1}


def test_unresolved_identity_does_not_query_product_tables():
    telemetry = QualityTelemetry()
    primary = FakePrimary(candidates=[])
    store = CanonicalReadShadowStore(primary, telemetry=telemetry)

    result = store.get_profile(42)

    assert result["game"] == "Warzone"
    assert primary.calls == [
        ("POST", "rpc/black_crown_eligible_identity_candidates")
    ]
    snapshot = telemetry.snapshot()["canonical_read_shadow"]
    assert snapshot["outcomes"] == {"identity_unresolved": 1}
    assert snapshot["comparisons"] == 0


def test_shadow_failure_is_isolated_from_live_read():
    telemetry = QualityTelemetry()
    primary = FakePrimary(canonical_error=True)
    store = CanonicalReadShadowStore(primary, telemetry=telemetry)

    assert store.get_profile(42)["game"] == "Warzone"
    snapshot = telemetry.snapshot()["canonical_read_shadow"]
    assert snapshot["outcomes"] == {"canonical_error": 1}
    assert snapshot["comparisons"] == 0


def test_zero_sample_rate_performs_no_shadow_network_call():
    telemetry = QualityTelemetry()
    primary = FakePrimary()
    store = CanonicalReadShadowStore(
        primary,
        sample_rate=0.0,
        telemetry=telemetry,
    )

    assert store.get_profile(42)["game"] == "Warzone"
    assert primary.calls == []
    snapshot = telemetry.snapshot()["canonical_read_shadow"]
    assert snapshot["outcomes"] == {"sample_skipped": 1}


def test_identity_lookup_is_cached_without_caching_user_content():
    telemetry = QualityTelemetry()
    primary = FakePrimary()
    store = CanonicalReadShadowStore(primary, telemetry=telemetry)

    store.get_profile(42)
    store.get_profile(42)

    identity_calls = [
        call for call in primary.calls
        if call[1] == "rpc/black_crown_eligible_identity_candidates"
    ]
    canonical_calls = [
        call for call in primary.calls
        if call[1] == "bco_players"
    ]
    assert len(identity_calls) == 1
    assert len(canonical_calls) == 2
    status = store.canonical_read_shadow_status()
    assert status["identity_cache_entries"] == 1
    assert OWNER_ID not in repr(status)


def test_conflicting_singleton_rows_are_ambiguous_and_legacy_wins():
    telemetry = QualityTelemetry()
    primary = FakePrimary(
        canonical_profile_rows=[
            {
                "profile": {"game": "Black Ops 7"},
                "updated_at": "2026-08-20",
            },
            {
                "profile": {"game": "Warzone"},
                "updated_at": "2026-08-19",
            },
        ]
    )
    store = CanonicalReadShadowStore(primary, telemetry=telemetry)

    assert store.get_profile(42)["game"] == "Warzone"
    snapshot = telemetry.snapshot()["canonical_read_shadow"]
    assert snapshot["outcomes"] == {"canonical_ambiguous": 1}


def test_factory_installs_shadow_wrapper_without_network_call():
    settings = SimpleNamespace(
        memory_max_turns=20,
        storage_backend="supabase",
        storage_timeout_s=8.0,
        storage_outbox_max=500,
        storage_replay_batch=50,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-secret-not-real",
        supabase_schema="public",
        canonical_read_shadow_enabled=True,
        canonical_read_shadow_sample_rate=0.25,
        canonical_read_identity_cache_ttl_s=120,
        canonical_read_identity_negative_cache_ttl_s=5,
        canonical_read_identity_cache_max_entries=1000,
    )

    store = build_store(settings)
    try:
        assert isinstance(store, PersistentResilientStore)
        assert isinstance(store.primary, CanonicalReadShadowStore)
        status = store.primary.canonical_read_shadow_status()
        assert status["enabled"] is True
        assert status["sample_rate"] == 0.25
        assert status["returns_legacy"] is True
    finally:
        store.close()
