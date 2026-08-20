from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("migrations/007_canonical_ownership_backfill_serialization.sql")


def _compact_sql() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )
    return " ".join(without_comments.casefold().split())


def test_backfill_runs_are_serialized_by_a_server_only_row_lock():
    sql = _compact_sql()

    assert "black_crown_ownership_migration_lock" in sql
    assert "check (lock_key = 'bco-canonical-owner-v1')" in sql
    assert "for update" in sql
    assert "black_crown_ownership_runs_serialize" in sql
    assert "before insert" in sql
    assert "on public.black_crown_ownership_migration_runs" in sql
    assert "execute function public.black_crown_serialize_ownership_migration_run()" in sql
    assert "canonical ownership migration lock is unavailable" in sql


def test_serialization_surface_is_browser_denied_and_idempotent_to_install():
    sql = _compact_sql()

    assert "create table if not exists public.black_crown_ownership_migration_lock" in sql
    assert "on conflict (lock_key) do nothing" in sql
    assert "alter table public.black_crown_ownership_migration_lock enable row level security" in sql
    assert "revoke all on table public.black_crown_ownership_migration_lock from public, anon, authenticated" in sql
    assert "create policy black_crown_ownership_lock_browser_deny" in sql
    assert "grant execute on function public.black_crown_serialize_ownership_migration_run() to service_role" in sql
    assert "if not exists ( select 1 from pg_trigger" in sql

    for pattern in (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
    ):
        assert re.search(pattern, sql) is None
