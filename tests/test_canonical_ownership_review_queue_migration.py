from __future__ import annotations

import re
from pathlib import Path


MIGRATION = Path("migrations/011_canonical_ownership_review_queue.sql")


def _sql_without_comments() -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    return "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )


def _compact() -> str:
    return " ".join(_sql_without_comments().casefold().split())


def _function_body(sql: str, name: str) -> str:
    marker = f"create or replace function public.{name}"
    return sql.split(marker, 1)[1].split("$function$;", 1)[0]


def test_review_queue_is_additive_and_does_not_mutate_product_ownership():
    sql = _compact()

    for relation in (
        "black_crown_ownership_resolution_cases",
        "black_crown_ownership_resolution_events",
        "black_crown_ownership_resolution_queue",
    ):
        assert relation in sql

    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\bdrop\s+column\b",
        r"\btruncate\b",
        r"alter\s+column\s+black_crown_user_id\s+set\s+not\s+null",
    )
    for pattern in destructive_patterns:
        assert re.search(pattern, sql) is None

    protected_relations = (
        "black_crown_accounts",
        "black_crown_identities",
        "black_crown_identity_events",
        "bco_players",
        "bco_messages",
        "bco_episodes",
        "bco_player_mistakes",
        "bco_mistake_receipts",
        "bco_training_sessions",
        "bco_progression_events",
        "bco_user_activity",
        "blackcrown_entitlements",
        "blackcrown_account_links",
        "blackcrown_account_link_events",
    )
    for relation in protected_relations:
        assert re.search(
            rf"\b(?:insert\s+into|update|delete\s+from)\s+public\.{relation}\b",
            sql,
        ) is None

    assert "set black_crown_user_id" not in sql
    assert "insert into public.black_crown_identities" not in sql
    assert "insert into public.black_crown_accounts" not in sql
    assert "update public.blackcrown_entitlements" not in sql


def test_review_workflow_is_staged_disabled_with_a_dedicated_rollback_flag():
    sql = _compact()

    assert "'ownership_resolution_review', false" in sql
    assert "phase_2d_staged_disabled" in sql
    assert "black_crown_set_ownership_review_enabled" in sql
    assert "if p_enabled is null" in sql
    assert "length(v_reason) < 8" in sql
    assert "length(v_reason) > 256" in sql
    assert sql.count("ownership review workflow is disabled") == 2
    assert sql.count("where flags.flag_key = 'ownership_resolution_review'") >= 4
    assert "review_enabled" in sql

    setter = _function_body(sql, "black_crown_set_ownership_review_enabled")
    assert "black_crown_ownership_runtime_flags" in setter
    assert "black_crown_ownership_resolution_cases" not in setter
    assert "black_crown_identities" not in setter
    assert "blackcrown_entitlements" not in setter
    assert "automatic_resolution_allowed', false" in setter
    assert "owner_write_allowed', false" in setter
    assert "entitlement_transfer_allowed', false" in setter


def test_tables_views_and_rpcs_are_server_only():
    sql = _compact()

    for table in (
        "black_crown_ownership_resolution_cases",
        "black_crown_ownership_resolution_events",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert (
            f"revoke all on table public.{table} "
            "from public, anon, authenticated"
        ) in sql
        assert f"{table}_browser_deny" in sql

    assert (
        "create or replace view public.black_crown_ownership_resolution_queue "
        "with (security_invoker = true)"
    ) in sql
    assert (
        "revoke all on table public.black_crown_ownership_resolution_queue "
        "from public, anon, authenticated"
    ) in sql
    assert (
        "grant select on table public.black_crown_ownership_resolution_queue "
        "to service_role"
    ) in sql

    functions = (
        "black_crown_set_ownership_review_enabled",
        "black_crown_refresh_ownership_resolution_cases",
        "black_crown_begin_ownership_confirmation",
        "black_crown_cancel_ownership_confirmation",
    )
    for function in functions:
        assert f"create or replace function public.{function}" in sql
        assert "security definer" in _function_body(sql, function)
        assert f"revoke all on function public.{function}" in sql
        assert f"grant execute on function public.{function}" in sql


def test_no_raw_provider_subject_is_stored_or_projected():
    sql = _compact()

    assert "legacy_subject_hash text not null" in sql
    assert "legacy_subject_hash ~ '^[0-9a-f]{64}$'" in sql
    assert "actor_ref_hash ~ '^[0-9a-f]{64}$'" in sql

    for forbidden_column in (
        "legacy_subject text",
        "provider_subject text",
        "telegram_user_id bigint",
        "chat_id bigint",
        "site_user_id text",
    ):
        assert forbidden_column not in sql

    assert "raw_subject_stored', false" in sql
    assert "cardinality(cases.candidate_user_ids)" in sql
    assert "proposed_owner_present" in sql
    queue = sql.split(
        "create or replace view public.black_crown_ownership_resolution_queue",
        1,
    )[1].split("revoke all on table", 1)[0]
    assert "candidate_count" in queue
    assert "candidate_user_ids," not in queue
    assert "proposed_black_crown_user_id," not in queue


def test_case_state_machine_cannot_resolve_or_apply_ownership():
    sql = _compact()

    assert (
        "case_state in ('open', 'blocked', 'awaiting_confirmation', "
        "'superseded')"
    ) in sql
    assert "case_state in ('resolved'" not in sql
    assert "automatic_resolution_allowed = false" in sql
    assert "owner_write_allowed = false" in sql
    assert "entitlement_transfer_allowed = false" in sql

    forbidden_api_markers = (
        "black_crown_confirm_ownership",
        "black_crown_apply_ownership",
        "black_crown_resolve_ownership_case",
    )
    for marker in forbidden_api_markers:
        assert marker not in sql

    assert "confirmation_proposed" in sql
    assert "confirmation_cancelled" in sql
    assert "owner_write_performed', false" in sql
    assert "identity_write_performed', false" in sql
    assert "entitlement_transfer_performed', false" in sql


def test_confirmation_proposal_is_revision_guarded_and_non_authoritative():
    sql = _compact()
    begin = _function_body(sql, "black_crown_begin_ownership_confirmation")
    cancel = _function_body(sql, "black_crown_cancel_ownership_confirmation")

    for body in (begin, cancel):
        assert "p_expected_revision is null" in body
        assert "p_expected_revision < 1" in body
        assert "for update" in body
        assert "v_case.revision <> p_expected_revision" in body
        assert "errcode = '40001'" in body
        assert "ownership review workflow is disabled" in body

    assert "account.account_status in ('active', 'provisional')" in begin
    assert "support_dual_confirmation" in begin
    assert "p_proposed_black_crown_user_id = any(v_case.candidate_user_ids)" in begin
    assert "case_state = 'awaiting_confirmation'" in begin
    assert "confirmation_state = 'pending'" in begin
    assert "set black_crown_user_id" not in begin
    assert "black_crown_identities" not in begin
    assert "blackcrown_entitlements" not in begin

    assert "case_state <> 'awaiting_confirmation'" in cancel
    assert "source_states && array['conflict', 'merge_pending']" in cancel
    assert "proposed_black_crown_user_id = null" in cancel
    assert "confirmation_state = 'not_started'" in cancel


def test_refresh_is_idempotent_concurrency_safe_and_never_silently_merges():
    sql = _compact()
    refresh = _function_body(sql, "black_crown_refresh_ownership_resolution_cases")

    assert "pg_advisory_xact_lock" in refresh
    assert "state.state <> 'resolved'" in refresh
    assert "array_agg(distinct state.scope order by state.scope)" in refresh
    assert "array_agg(distinct state.state order by state.state)" in refresh
    assert "on conflict (legacy_provider, legacy_subject_hash)" in refresh
    assert "target.case_state = 'awaiting_confirmation'" in refresh
    assert "case_state = 'superseded'" in refresh
    assert "source_no_longer_unresolved" in refresh
    assert "identity_conflict" in refresh
    assert "merge_pending" in refresh
    assert "owner_writes_performed', 0" in refresh
    assert "identity_writes_performed', 0" in refresh
    assert "entitlement_transfers_performed', 0" in refresh
    assert "select public.black_crown_refresh_ownership_resolution_cases()" in sql
