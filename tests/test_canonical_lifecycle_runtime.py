from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import httpx
import pytest

from app.services.storage.factory import (
    PersistentResilientStore,
    PersistentSupabaseStore,
)
from app.services.storage.memory import InMemoryStore


MIGRATION = Path("migrations/011_canonical_lifecycle_runtime.sql")
OWNER = "11111111-1111-1111-1111-111111111111"


def _sql_without_comments() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )


def _compact_sql() -> str:
    return " ".join(_sql_without_comments().casefold().split())


def _store(handler) -> PersistentSupabaseStore:
    store = PersistentSupabaseStore(
        url="https://example.supabase.co",
        service_role_key="server-secret",
    )
    old = store._client
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    old.close()
    return store


def test_migration_is_staged_additive_and_server_authoritative():
    sql = _compact_sql()

    assert "'canonical_lifecycle'" in sql
    assert "'canonical_lifecycle', false, 'phase_2d_staged_disabled'" in sql
    assert "black_crown_eligible_identity_candidates" in sql
    assert "cardinality(v_candidates)" in sql
    assert "telegram_user_ids bigint[]" in sql
    assert "identity.black_crown_user_id = v_owner" in sql
    assert "identity.provider = 'telegram'" in sql
    assert "identity.provider_subject ~ '^[1-9][0-9]{0,17}$'" in sql
    assert "p_telegram_user_id" in sql
    assert "p_black_crown_user_id" not in sql

    for function_name in (
        "black_crown_resolve_lifecycle_scope",
        "black_crown_clear_conversation",
        "black_crown_reset_player_profile",
        "black_crown_purge_product_data",
    ):
        assert f"revoke all on function public.{function_name}" in sql
        assert f"grant execute on function public.{function_name}" in sql
        assert "to service_role" in sql

    assert "create or replace view public.black_crown_lifecycle_runtime_status" in sql
    assert "with (security_invoker = true)" in sql
    assert "revoke all on table public.black_crown_lifecycle_runtime_status" in sql
    assert "grant select on table public.black_crown_lifecycle_runtime_status to service_role" in sql


def test_lifecycle_scope_is_canonical_only_after_explicit_enablement():
    sql = _compact_sql()

    canonical_gate = (
        "coalesce(v_scope.lifecycle_enabled, false) "
        "and v_scope.resolution_state = 'resolved' "
        "and v_scope.black_crown_user_id is not null"
    )
    assert sql.count(canonical_gate) == 3

    # Canonical mode covers both projected rows and legacy-only rows for every
    # server-owned Telegram identity already attached to the resolved account.
    assert sql.count("or chat_id = any(v_scope.telegram_user_ids)") >= 9
    assert (
        "where black_crown_user_id = v_scope.black_crown_user_id "
        "or telegram_user_id = any(v_scope.telegram_user_ids)"
    ) in sql

    # Disabled, unresolved and conflict paths stay exact-subject only.
    assert sql.count("where chat_id = p_telegram_user_id") >= 7
    assert "where telegram_user_id = p_telegram_user_id" in sql

    for marker in (
        "'canonical_scope_applied', v_canonical_scope",
        "'legacy_fallback_applied', not v_canonical_scope",
        "'resolution_state', v_scope.resolution_state",
        "'linked_telegram_subject_count', cardinality(v_scope.telegram_user_ids)",
    ):
        assert sql.count(marker) == 3


def test_purge_covers_product_state_but_preserves_account_authority():
    sql = _compact_sql()

    purge_definition = sql.split(
        "create or replace function public.black_crown_purge_product_data(",
        1,
    )[1].split("$function$;", 1)[0]

    for table in (
        "bco_messages",
        "bco_player_mistakes",
        "bco_mistake_receipts",
        "bco_episodes",
        "bco_training_sessions",
        "bco_progression_events",
        "bco_user_activity",
        "bco_players",
    ):
        assert f"delete from public.{table}" in purge_definition

    for protected_table in (
        "black_crown_accounts",
        "black_crown_identities",
        "blackcrown_account_links",
        "blackcrown_entitlements",
    ):
        assert re.search(
            rf"delete\s+from\s+public\.{protected_table}\b",
            purge_definition,
        ) is None

    assert "'account_preserved', true" in purge_definition
    assert "'identities_preserved', true" in purge_definition
    assert "'entitlements_preserved', true" in purge_definition


def test_public_storage_lifecycle_methods_do_not_accept_canonical_owner():
    for name in ("clear", "reset_profile", "purge_player"):
        signature = inspect.signature(getattr(PersistentSupabaseStore, name))
        assert "black_crown_user_id" not in signature.parameters
        assert "telegram_user_id" not in signature.parameters
        assert "chat_id" in signature.parameters


def test_lifecycle_operations_use_only_server_rpc_subject_contract():
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append((request.url.path, body))
        return httpx.Response(200, request=request, json={"ok": True})

    store = _store(handler)
    try:
        store.clear(42)
        store.reset_profile(42)
        store.purge_player(42)
    finally:
        store.close()

    assert seen == [
        (
            "/rest/v1/rpc/black_crown_clear_conversation",
            {"p_telegram_user_id": 42},
        ),
        (
            "/rest/v1/rpc/black_crown_reset_player_profile",
            {"p_telegram_user_id": 42},
        ),
        (
            "/rest/v1/rpc/black_crown_purge_product_data",
            {"p_telegram_user_id": 42},
        ),
    ]
    assert OWNER not in repr(seen)


@pytest.mark.parametrize(
    ("method", "new_rpc", "legacy_path", "legacy_method"),
    (
        (
            "clear",
            "black_crown_clear_conversation",
            "/rest/v1/bco_messages",
            "DELETE",
        ),
        (
            "reset_profile",
            "black_crown_reset_player_profile",
            "/rest/v1/bco_players",
            "DELETE",
        ),
        (
            "purge_player",
            "black_crown_purge_product_data",
            "/rest/v1/rpc/bco_purge_player",
            "POST",
        ),
    ),
)
def test_confirmed_missing_rpc_uses_only_staged_legacy_compatibility(
    method: str,
    new_rpc: str,
    legacy_path: str,
    legacy_method: str,
):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith(f"/rpc/{new_rpc}"):
            return httpx.Response(
                404,
                request=request,
                json={
                    "code": "PGRST202",
                    "message": "Could not find the function",
                },
            )
        return httpx.Response(204, request=request)

    store = _store(handler)
    try:
        getattr(store, method)(91)
    finally:
        store.close()

    assert len(seen) == 2
    assert seen[0].url.path.endswith(f"/rpc/{new_rpc}")
    assert seen[1].url.path == legacy_path
    assert seen[1].method == legacy_method
    if method == "purge_player":
        assert json.loads(seen[1].content.decode("utf-8")) == {"p_chat_id": 91}
    else:
        assert seen[1].url.params.get("chat_id") == "eq.91"
        assert seen[1].url.params.get("black_crown_user_id") is None


def test_non_function_postgrest_error_never_downgrades_to_legacy_delete():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            404,
            request=request,
            json={
                "code": "PGRST204",
                "message": "Could not find a request column",
            },
        )

    store = _store(handler)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            store.clear(92)
    finally:
        store.close()

    assert len(seen) == 1
    assert seen[0].url.path.endswith(
        "/rpc/black_crown_clear_conversation"
    )


def test_policy_or_server_failure_never_downgrades_to_direct_legacy_delete():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            503,
            request=request,
            json={"code": "XX000", "message": "server unavailable"},
        )

    store = _store(handler)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            store.clear(77)
    finally:
        store.close()

    assert len(seen) == 1
    assert seen[0].url.path.endswith(
        "/rpc/black_crown_clear_conversation"
    )


def test_resilient_store_queues_lifecycle_operation_on_server_failure():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, request=request, json={"code": "XX000"})

    primary = _store(handler)
    store = PersistentResilientStore(
        primary=primary,
        fallback=InMemoryStore(),
        outbox_max=20,
        replay_batch=5,
    )
    try:
        store.clear(88)
        status = store.recovery_status()
        assert status["outbox_pending"] == 1
        assert status["primary_available"] is False
        assert status["last_primary_error"] == "HTTPStatusError"
    finally:
        primary.close()

    assert calls == 1


def test_lifecycle_status_is_privacy_safe_and_owner_free():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(
            "/black_crown_lifecycle_runtime_status"
        )
        return httpx.Response(
            200,
            request=request,
            json=[{
                "schema_version": "bco-canonical-lifecycle-v1",
                "lifecycle_enabled": False,
                "lifecycle_reason": "phase_2d_staged_disabled",
                "lifecycle_updated_at": "2026-08-21T00:00:00Z",
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
                "provider_subject": "raw-subject-must-not-leak",
            }],
        )

    store = _store(handler)
    try:
        status = store.canonical_lifecycle_status()
    finally:
        store.close()

    assert status == {
        "schema": "bco-canonical-lifecycle-v1",
        "enabled": False,
        "mode": "legacy_subject",
        "reason": "phase_2d_staged_disabled",
        "updated_at": "2026-08-21T00:00:00Z",
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
    assert OWNER not in repr(status)
    assert "raw-subject" not in repr(status)
