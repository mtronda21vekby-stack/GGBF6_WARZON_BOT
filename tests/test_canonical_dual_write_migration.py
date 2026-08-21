from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("migrations/008_canonical_owner_dual_write_runtime.sql")
TARGET_TABLES = {
    "bco_players",
    "bco_messages",
    "bco_episodes",
    "bco_player_mistakes",
    "bco_mistake_receipts",
    "bco_progression_events",
    "bco_training_sessions",
    "bco_user_activity",
    "blackcrown_account_links",
    "blackcrown_account_link_events",
    "blackcrown_entitlements",
}


def _sql_without_line_comments() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )


def _compact_sql() -> str:
    return " ".join(_sql_without_line_comments().casefold().split())


def test_dual_write_runtime_is_additive_and_preserves_legacy_keys():
    sql = _compact_sql()

    for table in TARGET_TABLES:
        assert table in sql

    assert "before insert or update" in sql
    assert "black_crown_user_id" in sql

    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"\bdelete\s+from\s+public\.(?:bco_|blackcrown_)",
        r"alter\s+column\s+black_crown_user_id\s+set\s+not\s+null",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None

    for legacy_key in ("chat_id", "telegram_user_id", "site_user_id"):
        assert f"drop column {legacy_key}" not in sql


def test_dual_write_has_server_only_rollback_flag_and_status():
    sql = _compact_sql()

    assert "create table if not exists public.black_crown_ownership_runtime_flags" in sql
    assert "check (flag_key in ('canonical_dual_write'))" in sql
    assert "alter table public.black_crown_ownership_runtime_flags enable row level security" in sql
    assert (
        "revoke all on table public.black_crown_ownership_runtime_flags "
        "from public, anon, authenticated"
    ) in sql
    assert "black_crown_ownership_runtime_flags_browser_deny" in sql
    assert "grant select, update on table public.black_crown_ownership_runtime_flags to service_role" in sql

    assert "black_crown_set_ownership_runtime_flag" in sql
    assert "unsupported canonical ownership runtime flag" in sql
    assert "runtime flag change reason is required" in sql
    assert sql.count("if not coalesce(v_enabled, false)") == 3
    assert "case when tg_op = 'update' then v_old_owner else null end" in sql

    assert "create or replace view public.black_crown_ownership_runtime_status" in sql
    assert "with (security_invoker = true)" in sql
    assert "canonical_dual_write_enabled" in sql
    assert "installed_trigger_count" in sql
    assert "11::integer as expected_trigger_count" in sql
    assert (
        "revoke all on table public.black_crown_ownership_runtime_status "
        "from public, anon, authenticated"
    ) in sql


def test_identity_authority_is_server_resolved_and_client_owner_is_ignored():
    sql = _compact_sql()

    assert "black_crown_eligible_identity_candidates" in sql
    assert "from public.black_crown_identities as identity" in sql
    assert "join public.black_crown_accounts as account" in sql
    assert "identity.status in ('active', 'provisional')" in sql
    assert "account.account_status in ('active', 'provisional')" in sql

    # The migration accepts legacy provider subjects only. It has no RPC or
    # trigger argument through which a browser can assert a canonical owner.
    assert "p_black_crown_user_id" not in sql
    assert "p_candidate_user_id" not in sql
    assert "to_jsonb(new) ->> 'black_crown_user_id'" not in sql
    assert "jsonb_populate_record" in sql
    assert "'client_owner_authority', false" in sql
    assert "'owner_overwrite_allowed', false" in sql
    assert "'silent_merge_allowed', false" in sql


def test_all_current_user_owned_surfaces_receive_dual_write_triggers():
    sql = _compact_sql()

    generic_targets = {
        "bco_players": ("telegram", "chat_id", "product_state"),
        "bco_messages": ("telegram", "chat_id", "product_state"),
        "bco_episodes": ("telegram", "chat_id", "product_state"),
        "bco_player_mistakes": ("telegram", "chat_id", "product_state"),
        "bco_mistake_receipts": ("telegram", "chat_id", "product_state"),
        "bco_progression_events": ("telegram", "chat_id", "product_state"),
        "bco_training_sessions": ("telegram", "chat_id", "product_state"),
        "bco_user_activity": ("telegram", "telegram_user_id", "analytics_activity"),
        "blackcrown_entitlements": ("website_auth", "site_user_id", "entitlement"),
    }
    for table, (provider, subject_column, scope) in generic_targets.items():
        assert f"('{table}', '{provider}', '{subject_column}', '{scope}')" in sql

    assert "blackcrown_account_links_canonical_owner_dual_write" in sql
    assert "black_crown_apply_account_link_owner" in sql
    assert "blackcrown_account_link_events_canonical_owner_dual_write" in sql
    assert "black_crown_apply_account_link_event_owner" in sql
    assert "execute function public.black_crown_apply_single_provider_owner" in sql


def test_conflicts_never_transfer_owner_or_entitlement_silently():
    sql = _compact_sql()

    assert "v_owner := v_old_owner" in sql
    assert "existing_owner_differs_from_eligible_identity" in sql
    assert "existing_link_owner_differs_from_identity_agreement" in sql
    assert "existing_event_owner_differs_from_identity" in sql

    assert "website_and_telegram_identities_agree" in sql
    assert "website_and_telegram_identities_disagree" in sql
    assert "v_state := 'merge_pending'" in sql
    assert "'entitlement_transfer_allowed', false" in sql
    assert "black_crown_record_owner_conflict_event" in sql
    assert "conflict_fingerprint" in sql
    assert "where not exists" in sql

    # Entitlements resolve only from the verified Website provider subject.
    assert "('blackcrown_entitlements', 'website_auth', 'site_user_id', 'entitlement')" in sql


def test_migration_audit_is_privacy_safe_and_functions_are_not_public():
    sql = _compact_sql()

    assert "black_crown_legacy_subject_hash" in sql
    assert "'raw_subject_stored', false" in sql
    assert "provider_subject_hash" in sql
    assert "raw_subject text" not in sql

    functions = (
        "black_crown_set_ownership_runtime_flag(text, boolean, text)",
        "black_crown_normalize_owner_candidates(uuid[])",
        "black_crown_eligible_identity_candidates(text, text)",
        "black_crown_apply_single_provider_owner()",
        "black_crown_apply_account_link_owner()",
        "black_crown_apply_account_link_event_owner()",
    )
    for signature in functions:
        assert f"revoke all on function public.{signature}" in sql
        assert f"grant execute on function public.{signature} to service_role" in sql
