from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("migrations/009_canonical_owner_dual_read_runtime.sql")
ROUTER = Path("app/services/storage/canonical_read.py")
FACTORY = Path("app/services/storage/factory.py")
READINESS = Path("app/observability/readiness.py")


def _compact(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )
    return " ".join(without_comments.casefold().split())


def test_dual_read_migration_is_additive_and_staged_disabled():
    sql = _compact(MIGRATION)

    assert "'canonical_dual_write', 'canonical_dual_read'" in sql
    assert "'canonical_dual_read', false, 'phase_2c_staged_disabled'" in sql
    assert "bco-canonical-read-v1" in sql
    assert "bco-canonical-owner-v3" in sql

    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"\bdelete\s+from\s+public\.(?:bco_|blackcrown_|black_crown_)",
        r"alter\s+column\s+black_crown_user_id\s+set\s+not\s+null",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None


def test_read_owner_resolution_is_server_only_and_read_only():
    sql = _compact(MIGRATION)
    marker = (
        "create or replace function public.black_crown_resolve_read_owner("
    )
    function_body = sql.split(marker, 1)[1].split("$function$;", 1)[0]

    assert "security definer" in function_body
    assert "black_crown_eligible_identity_candidates" in function_body
    assert "resolution_state" in function_body
    assert "candidate_count" in function_body
    assert "insert into" not in function_body
    assert "update public." not in function_body
    assert "delete from" not in function_body
    assert "black_crown_resolve_telegram_identity" not in function_body

    assert (
        "revoke all on function public.black_crown_resolve_read_owner(text, text) "
        "from public, anon, authenticated"
    ) in sql
    assert (
        "grant execute on function public.black_crown_resolve_read_owner(text, text) "
        "to service_role"
    ) in sql


def test_runtime_flag_supports_independent_non_destructive_rollback():
    sql = _compact(MIGRATION)

    assert (
        "p_flag_key not in ('canonical_dual_write', 'canonical_dual_read')"
        in sql
    )
    assert "runtime flag change reason is required" in sql
    assert "canonical_dual_read_enabled" in sql
    assert "canonical_dual_read_updated_at" in sql
    assert "canonical_read_schema" in sql
    assert "grant select on table public.black_crown_ownership_runtime_status to service_role" in sql
    assert "revoke all on table public.black_crown_ownership_runtime_status from public, anon, authenticated" in sql


def test_application_read_path_never_accepts_caller_owner_authority():
    router = ROUTER.read_text(encoding="utf-8")
    factory = FACTORY.read_text(encoding="utf-8")

    assert "rpc/black_crown_resolve_read_owner" in router
    assert 'json={"p_provider": "telegram", "p_subject": str(subject)}' in router
    assert "black_crown_user_id" in router
    assert "legacy_fallback_" in router
    assert "identity_conflict" in router
    assert "canonical_ambiguous" in router
    assert "canonical_query_error" in router
    assert "coverage_incomplete" in router
    assert "mapping_conflict" in router
    assert "schema_mismatch" in router

    # Public storage methods continue to receive the legacy trusted Telegram
    # subject only. No method accepts a caller canonical ID argument.
    forbidden_signature = re.compile(
        r"def\s+(?:get|get_profile|get_summary|get_derived_intelligence|"
        r"list_mistake_stats|list_episodes|list_training_sessions|"
        r"list_progression_events)\([^)]*black_crown_user_id"
    )
    assert forbidden_signature.search(factory) is None
    assert "prime_telegram_identity" in factory
    assert "Destructive lifecycle behavior remains legacy-scoped in Phase 2C" in factory


def test_health_details_exposes_only_privacy_safe_read_metrics():
    readiness = READINESS.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")

    for marker in (
        '"canonical_owner_read_capability"',
        '"canonical_owner_first_reads"',
        '"canonical_owner_legacy_fallback"',
        '"canonical_read": canonical_read_snapshot',
    ):
        assert marker in readiness

    identity_block = readiness.split('"identity": {', 1)[1].split("},", 1)[0]
    assert '"product_owner_key"' not in identity_block
    assert '"canonical_read_mode"' not in identity_block
    assert '"canonical_read_client_authority"' not in identity_block

    assert '"black_crown_user_id":' not in router.split("def snapshot", 1)[1]
    assert '"control_state"' in router
    assert '"canonical_hits"' in router
    assert '"legacy_fallbacks"' in router
    assert '"coverage_ready_tables"' in router
    assert '"coverage_blocked_tables"' in router
    assert "rows[0].get(\"reason\")" not in router
