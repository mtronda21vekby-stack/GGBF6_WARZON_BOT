-- BLACK CROWN canonical ownership dual-read runtime (Phase 2C)
--
-- This migration adds only the server-owned control plane for canonical-first
-- reads. Legacy keys remain present and remain the mandatory fallback path.
-- Application code never accepts a caller-supplied black_crown_user_id.
--
-- Rollback: set canonical_dual_read=false through the service-role RPC. No
-- product row, identity, entitlement, Player Brain row or history row is
-- deleted or rewritten by this migration.

alter table public.black_crown_ownership_runtime_flags
  drop constraint if exists black_crown_ownership_runtime_flag_key_check;

alter table public.black_crown_ownership_runtime_flags
  add constraint black_crown_ownership_runtime_flag_key_check
  check (flag_key in ('canonical_dual_write', 'canonical_dual_read'));

insert into public.black_crown_ownership_runtime_flags (
  flag_key,
  enabled,
  reason,
  updated_at
) values (
  'canonical_dual_read',
  false,
  'phase_2c_staged_disabled',
  now()
)
on conflict (flag_key) do nothing;

create or replace function public.black_crown_set_ownership_runtime_flag(
  p_flag_key text,
  p_enabled boolean,
  p_reason text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_reason text := left(trim(coalesce(p_reason, '')), 512);
  v_result jsonb;
begin
  if p_flag_key not in ('canonical_dual_write', 'canonical_dual_read') then
    raise exception using
      errcode = '22023',
      message = 'unsupported canonical ownership runtime flag';
  end if;
  if v_reason = '' then
    raise exception using
      errcode = '22023',
      message = 'runtime flag change reason is required';
  end if;

  insert into public.black_crown_ownership_runtime_flags (
    flag_key,
    enabled,
    reason,
    updated_at
  ) values (
    p_flag_key,
    coalesce(p_enabled, false),
    v_reason,
    now()
  )
  on conflict (flag_key) do update set
    enabled = excluded.enabled,
    reason = excluded.reason,
    updated_at = now();

  select jsonb_build_object(
    'flag_key', flags.flag_key,
    'enabled', flags.enabled,
    'reason', flags.reason,
    'updated_at', flags.updated_at
  )
  into v_result
  from public.black_crown_ownership_runtime_flags as flags
  where flags.flag_key = p_flag_key;

  return v_result;
end;
$function$;

revoke all on function public.black_crown_set_ownership_runtime_flag(text, boolean, text)
  from public, anon, authenticated;
grant execute on function public.black_crown_set_ownership_runtime_flag(text, boolean, text)
  to service_role;

create or replace function public.black_crown_resolve_read_owner(
  p_provider text,
  p_subject text
)
returns table (
  resolution_state text,
  black_crown_user_id uuid,
  candidate_count integer,
  schema_version text
)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $function$
declare
  v_provider text := trim(coalesce(p_provider, ''));
  v_candidates uuid[];
begin
  if v_provider not in ('telegram', 'website_auth') then
    raise exception using
      errcode = '22023',
      message = 'unsupported canonical identity provider';
  end if;

  v_candidates := public.black_crown_eligible_identity_candidates(
    v_provider,
    trim(coalesce(p_subject, ''))
  );

  return query
  select
    case cardinality(v_candidates)
      when 0 then 'unresolved'::text
      when 1 then 'resolved'::text
      else 'conflict'::text
    end,
    case
      when cardinality(v_candidates) = 1 then v_candidates[1]
      else null::uuid
    end,
    cardinality(v_candidates)::integer,
    'bco-canonical-read-v1'::text;
end;
$function$;

revoke all on function public.black_crown_resolve_read_owner(text, text)
  from public, anon, authenticated;
grant execute on function public.black_crown_resolve_read_owner(text, text)
  to service_role;

create or replace view public.black_crown_ownership_runtime_status
with (security_invoker = true)
as
select
  'bco-canonical-owner-v3'::text as schema_version,
  coalesce(write_flag.enabled, false) as canonical_dual_write_enabled,
  write_flag.reason as canonical_dual_write_reason,
  write_flag.updated_at as canonical_dual_write_updated_at,
  (
    select count(*)::integer
    from pg_trigger as trigger
    join pg_class as relation
      on relation.oid = trigger.tgrelid
    join pg_namespace as namespace
      on namespace.oid = relation.relnamespace
    where namespace.nspname = 'public'
      and trigger.tgname like '%_canonical_owner_dual_write'
      and not trigger.tgisinternal
  ) as installed_trigger_count,
  11::integer as expected_trigger_count,
  (
    select coalesce(
      jsonb_object_agg(
        coverage.table_name,
        jsonb_build_object(
          'total_rows', coverage.total_rows,
          'canonical_rows', coverage.canonical_rows,
          'legacy_only_rows', coverage.legacy_only_rows,
          'coverage_percent', coverage.coverage_percent
        )
      ),
      '{}'::jsonb
    )
    from public.black_crown_ownership_coverage as coverage
  ) as coverage,
  (
    select coalesce(
      jsonb_object_agg(state.state, state.count),
      '{}'::jsonb
    )
    from (
      select migration.state, count(*)::bigint as count
      from public.black_crown_ownership_migration_state as migration
      group by migration.state
    ) as state
  ) as mapping_state,
  coalesce((
    select read_flag.enabled
    from public.black_crown_ownership_runtime_flags as read_flag
    where read_flag.flag_key = 'canonical_dual_read'
  ), false) as canonical_dual_read_enabled,
  (
    select read_flag.reason
    from public.black_crown_ownership_runtime_flags as read_flag
    where read_flag.flag_key = 'canonical_dual_read'
  ) as canonical_dual_read_reason,
  (
    select read_flag.updated_at
    from public.black_crown_ownership_runtime_flags as read_flag
    where read_flag.flag_key = 'canonical_dual_read'
  ) as canonical_dual_read_updated_at,
  'bco-canonical-read-v1'::text as canonical_read_schema
from public.black_crown_ownership_runtime_flags as write_flag
where write_flag.flag_key = 'canonical_dual_write';

revoke all on table public.black_crown_ownership_runtime_status
  from public, anon, authenticated;
grant select on table public.black_crown_ownership_runtime_status
  to service_role;

comment on function public.black_crown_resolve_read_owner(text, text) is
  'Service-role read-only canonical owner resolution. Does not create or merge accounts and never returns the raw provider subject.';
comment on view public.black_crown_ownership_runtime_status is
  'Service-role canonical ownership write/read flags, trigger readiness and coverage.';
