from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path(
    "migrations/010_canonical_read_shadow_evidence_hardening.sql"
)
CONTROL = Path("app/services/storage/canonical_shadow_control.py")
SHADOW = Path("app/services/storage/canonical_shadow.py")
QUALITY = Path("app/observability/quality.py")


def _compact(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    body = "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )
    return " ".join(body.casefold().split())


def test_migration_is_additive_status_only_and_preserves_legacy_authority():
    sql = _compact(MIGRATION)

    assert "bco-canonical-read-shadow-v2" in sql
    assert "shadow_surface_coverage_ready" in sql
    assert "promotion_ready" in sql
    assert "promotion_blockers" in sql
    assert "coverage_incomplete" in sql
    assert "identity_conflict" in sql
    assert "merge_pending" in sql
    assert "dual_write_disabled" in sql

    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\bupdate\s+public\.(?:bco_|blackcrown_|black_crown_)",
        r"\binsert\s+into\s+public\.(?:bco_|blackcrown_|black_crown_)",
        r"alter\s+column\s+black_crown_user_id\s+set\s+not\s+null",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None


def test_status_view_uses_only_privacy_safe_aggregate_coverage():
    sql = _compact(MIGRATION)

    for table in (
        "bco_players",
        "bco_messages",
        "bco_episodes",
        "bco_player_mistakes",
        "bco_training_sessions",
        "bco_progression_events",
    ):
        assert f"'{table}'" in sql

    assert "provider_subject" not in sql
    assert "black_crown_user_id" not in sql
    assert "profile" not in sql
    assert "content" not in sql
    assert "with (security_invoker = true)" in sql
    assert (
        "revoke all on table public.black_crown_canonical_read_runtime_status "
        "from public, anon, authenticated"
    ) in sql
    assert (
        "grant select on table public.black_crown_canonical_read_runtime_status "
        "to service_role"
    ) in sql


def test_control_never_reads_or_publishes_free_form_database_reason():
    control = CONTROL.read_text(encoding="utf-8")

    assert '"black_crown_canonical_read_runtime_status"' in control
    assert "shadow_read_reason" not in control
    assert "black_crown_ownership_runtime_flags" not in control
    assert '"mapping_conflict"' in control
    assert '"schema_mismatch"' in control
    assert '"dual_write_disabled"' in control
    assert "_sanitize_blockers" in control
    assert "promotion_ready" in control
    assert "coverage_ready" in control


def test_resolved_owner_cache_is_prohibited_and_negative_cache_is_explicit():
    shadow = SHADOW.read_text(encoding="utf-8")

    assert "A successful owner is never retained beyond the current read" in shadow
    assert "self._identity_cache.pop(int(chat_id), None)" in shadow
    assert "resolved_identity_cache_enabled" in shadow
    assert "negative_identity_cache_entries" in shadow
    assert "def resolve_telegram_identity" in shadow
    assert "self.invalidate_identity_cache" in shadow


def test_quality_telemetry_accepts_only_known_promotion_blockers():
    quality = QUALITY.read_text(encoding="utf-8")

    assert "_CANONICAL_PROMOTION_BLOCKERS" in quality
    assert "_sanitize_promotion_blockers" in quality
    assert '"promotion_ready"' in quality
    assert '"promotion_blockers"' in quality
    assert '"coverage_ready"' in quality
    assert '"identity_conflicts"' in quality
    assert '"merge_pending"' in quality
