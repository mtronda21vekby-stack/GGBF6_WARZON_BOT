from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("migrations/006_canonical_product_ownership_foundation.sql")
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
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))


def _compact_sql() -> str:
    return " ".join(_sql_without_line_comments().casefold().split())


def test_canonical_ownership_foundation_is_additive_and_keeps_legacy_keys():
    sql = _compact_sql()

    for table in TARGET_TABLES:
        assert f"'{table}'" in sql

    assert "add column if not exists black_crown_user_id uuid null" in sql
    assert "foreign key (black_crown_user_id)" in sql
    assert "references public.black_crown_accounts (black_crown_user_id)" in sql
    assert "where black_crown_user_id is not null" in sql

    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"\bdelete\s+from\s+public\.(?:bco_|blackcrown_)",
        r"alter\s+column\s+black_crown_user_id\s+set\s+not\s+null",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None

    assert "drop column chat_id" not in sql
    assert "drop column telegram_user_id" not in sql
    assert "drop column site_user_id" not in sql


def test_migration_state_is_privacy_safe_and_browser_denied():
    sql = _compact_sql()
    state_definition = sql.split(
        "create table if not exists public.black_crown_ownership_migration_state (",
        1,
    )[1].split(");", 1)[0]

    assert "legacy_subject_hash text not null" in state_definition
    assert "legacy_subject text" not in state_definition
    assert "candidate_user_ids uuid[]" in state_definition
    assert "state in ('resolved', 'unresolved', 'conflict', 'merge_pending')" in state_definition
    assert "black_crown_ownership_state_owner_check" in state_definition

    for relation in (
        "black_crown_ownership_migration_state",
        "black_crown_ownership_migration_runs",
    ):
        assert f"alter table public.{relation} enable row level security" in sql
        assert f"revoke all on table public.{relation} from public, anon, authenticated" in sql

    assert "raw_subject_stored', false" in sql
    assert "silent_merge_allowed', false" in sql
    assert "entitlement_transfer_allowed', false" in sql
    assert "grant execute on function public.black_crown_backfill_product_ownership(integer) to service_role" in sql
    assert "grant execute on function public.black_crown_refresh_ownership_migration_state() to service_role" in sql


def test_backfill_is_resumable_and_never_overwrites_an_owner():
    sql = _compact_sql()

    assert "greatest(1, least(coalesce(p_batch_size, 5000), 50000))" in sql
    assert "black_crown_ownership_migration_runs" in sql
    assert "schema_version', 'bco-canonical-owner-v1'" in sql
    assert "select public.black_crown_backfill_product_ownership(50000)" in sql

    # Generic state, account links and link-event projections all retain this guard.
    assert sql.count("black_crown_user_id is null") >= 10
    assert "set black_crown_user_id = candidates.black_crown_user_id" in sql
    assert "where runs.run_id = v_run_id" in sql
    assert "black_crown_backfill_product_ownership.run_id" not in sql


def test_conflicts_never_auto_merge_or_move_premium():
    sql = _compact_sql()

    assert "website_owner <> telegram_owner then 'merge_pending'" in sql
    assert "website_owner = telegram_owner then website_owner else null" in sql
    assert "telegram_identity.black_crown_user_id = website_identity.black_crown_user_id" in sql
    assert "event_type" in sql
    assert "'merge_pending'" in sql
    assert "public.black_crown_identity_events" in sql
    assert "entitlement_transfer_allowed', false" in sql

    # Existing entitlements project only through verified Website identity, not a
    # Telegram/browser-submitted canonical ID.
    assert "('blackcrown_entitlements', 'site_user_id', 'website_auth')" in sql
    assert "identity.provider = %l" in sql
    assert "identity.status = 'active'" in sql


def test_coverage_and_analytics_authority_are_explicit():
    sql = _compact_sql()

    assert "create or replace view public.black_crown_ownership_coverage" in sql
    assert "coverage_percent" in sql
    assert "legacy_only_rows" in sql
    for table in TARGET_TABLES:
        assert table in sql

    assert "alter table public.bco_user_activity enable row level security" in sql
    assert "create policy bco_user_activity_server_only" in sql
    assert "revoke all on table public.bco_user_activity from anon, authenticated" in sql
