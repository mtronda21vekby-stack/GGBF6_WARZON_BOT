-- BLACK CROWN canonical read shadow evidence hardening (Phase 2C.1)
--
-- Additive status-only migration. Legacy reads remain authoritative. This does
-- not enable canonical primary reads, change product ownership, merge accounts,
-- transfer entitlements, or rewrite player state.

create or replace view public.black_crown_canonical_read_runtime_status
with (security_invoker = true)
as
with flag as (
  select
    enabled,
    reason,
    updated_at
  from public.black_crown_ownership_runtime_flags
  where flag_key = 'canonical_shadow_read'
),
ownership as (
  select
    count(*) filter (where state = 'resolved')::bigint as resolved_count,
    count(*) filter (where state = 'unresolved')::bigint as unresolved_count,
    count(*) filter (where state = 'conflict')::bigint as conflict_count,
    count(*) filter (where state = 'merge_pending')::bigint as merge_pending_count
  from public.black_crown_ownership_migration_state
),
shadow_coverage as (
  select
    coalesce(
      jsonb_object_agg(
        coverage.table_name,
        jsonb_build_object(
          'total_rows', coverage.total_rows,
          'canonical_rows', coverage.canonical_rows,
          'legacy_only_rows', coverage.legacy_only_rows,
          'coverage_percent', coverage.coverage_percent
        )
        order by coverage.table_name
      ) filter (
        where coverage.table_name in (
          'bco_players',
          'bco_messages',
          'bco_episodes',
          'bco_player_mistakes',
          'bco_training_sessions',
          'bco_progression_events'
        )
      ),
      '{}'::jsonb
    ) as coverage,
    coalesce(
      bool_and(
        coverage.legacy_only_rows = 0
        and coverage.canonical_rows = coverage.total_rows
      ) filter (
        where coverage.table_name in (
          'bco_players',
          'bco_messages',
          'bco_episodes',
          'bco_player_mistakes',
          'bco_training_sessions',
          'bco_progression_events'
        )
      ),
      false
    ) as shadow_surface_coverage_ready
  from public.black_crown_ownership_coverage as coverage
),
status as (
  select
    'bco-canonical-read-shadow-v2'::text as schema_version,
    coalesce(flag.enabled, false) as shadow_read_enabled,
    flag.reason as shadow_read_reason,
    flag.updated_at as shadow_read_updated_at,
    coalesce((
      select runtime.enabled
      from public.black_crown_ownership_runtime_flags as runtime
      where runtime.flag_key = 'canonical_dual_write'
    ), false) as dual_write_enabled,
    ownership.resolved_count,
    ownership.unresolved_count,
    ownership.conflict_count,
    ownership.merge_pending_count,
    shadow_coverage.coverage,
    shadow_coverage.shadow_surface_coverage_ready
  from flag
  cross join ownership
  cross join shadow_coverage
)
select
  status.*,
  (
    status.shadow_read_enabled
    and status.dual_write_enabled
    and status.conflict_count = 0
    and status.merge_pending_count = 0
    and status.shadow_surface_coverage_ready
  ) as promotion_ready,
  array_remove(
    array[
      case when not status.shadow_read_enabled then 'shadow_disabled' end,
      case when not status.dual_write_enabled then 'dual_write_disabled' end,
      case when status.conflict_count > 0 then 'identity_conflict' end,
      case when status.merge_pending_count > 0 then 'merge_pending' end,
      case when not status.shadow_surface_coverage_ready then 'coverage_incomplete' end
    ]::text[],
    null
  ) as promotion_blockers
from status;

revoke all on table public.black_crown_canonical_read_runtime_status
  from public, anon, authenticated;
grant select on table public.black_crown_canonical_read_runtime_status
  to service_role;

comment on view public.black_crown_canonical_read_runtime_status is
  'Service-role canonical shadow control, conflict state, privacy-safe coverage and non-authoritative promotion blockers. Legacy remains read authority.';
