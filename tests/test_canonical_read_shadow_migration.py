from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("migrations/009_canonical_read_shadow_runtime.sql")


def _compact_sql() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )
    return " ".join(without_comments.casefold().split())


def test_shadow_migration_is_additive_and_preserves_legacy_authority():
    sql = _compact_sql()

    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"\bdelete\s+from\s+public\.(?:bco_|blackcrown_)",
        r"alter\s+column\s+black_crown_user_id\s+set\s+not\s+null",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None

    assert "canonical_shadow_read" in sql
    assert "canonical_dual_write" in sql
    assert "drop column chat_id" not in sql
    assert "drop column telegram_user_id" not in sql
    assert "drop column site_user_id" not in sql
    assert "insert into public.black_crown_accounts" not in sql
    assert "insert into public.black_crown_identities" not in sql


def test_read_and_write_controls_are_independent_and_server_only():
    sql = _compact_sql()

    assert (
        "check (flag_key in ('canonical_dual_write', "
        "'canonical_shadow_read'))"
    ) in sql
    assert (
        "p_flag_key not in ('canonical_dual_write', "
        "'canonical_shadow_read')"
    ) in sql
    assert (
        "'canonical_shadow_read', true, "
        "'phase_2c_initial_enable'"
    ) in sql
    assert (
        "revoke all on function "
        "public.black_crown_set_ownership_runtime_flag( "
        "text, boolean, text ) from public, anon, authenticated"
    ) in sql
    assert (
        "grant execute on function "
        "public.black_crown_set_ownership_runtime_flag( "
        "text, boolean, text ) to service_role"
    ) in sql


def test_runtime_status_view_is_service_role_only_and_privacy_safe():
    sql = _compact_sql()

    assert (
        "create or replace view "
        "public.black_crown_canonical_read_runtime_status"
    ) in sql
    assert "with (security_invoker = true)" in sql
    assert "shadow_read_enabled" in sql
    assert "dual_write_enabled" in sql
    assert "resolved_mappings" in sql
    assert "unresolved_mappings" in sql
    assert "conflict_mappings" in sql
    assert "merge_pending_mappings" in sql
    assert "provider_subject" not in sql
    assert "black_crown_user_id" not in sql
    assert (
        "revoke all on table "
        "public.black_crown_canonical_read_runtime_status "
        "from public, anon, authenticated"
    ) in sql
    assert (
        "grant select on table "
        "public.black_crown_canonical_read_runtime_status "
        "to service_role"
    ) in sql
