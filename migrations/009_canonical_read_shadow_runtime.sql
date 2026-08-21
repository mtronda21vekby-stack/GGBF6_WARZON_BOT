-- BLACK CROWN canonical read shadow runtime (Phase 2C)
--
-- This migration does not switch read authority. It adds an independent,
-- service-role operational flag for comparison-only canonical reads.
-- Existing legacy keys, canonical projections and dual-write triggers remain.

alter table public.black_crown_ownership_runtime_flags
  drop constraint if exists black_crown_ownership_runtime_flag_key_check;

alter table public.black_crown_ownership_runtime_flags
  add constraint black_crown_ownership_runtime_flag_key_check
  check (flag_key in ('canonical_dual_write', 'canonical_shadow_read'));

insert into public.black_crown_ownership_runtime_flags (
  flag_key,
  enabled,
  reason,
  updated_at
) values (
  'canonical_shadow_read',
  true,
  'phase_2c_initial_enable',
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
  if p_flag_key not in ('canonical_dual_write', 'canonical_shadow_read') then
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

revoke all on function public.black_crown_set_ownership_runtime_flag(
  text,
  boolean,
  text
) from public, anon, authenticated;
grant execute on function public.black_crown_set_ownership_runtime_flag(
  text,
  boolean,
  text
) to service_role;

create or replace view public.black_crown_canonical_read_runtime_status
with (security_invoker = true)
as
select
  'bco-canonical-read-shadow-v1'::text as schema_version,
  shadow.enabled as shadow_read_enabled,
  shadow.reason as shadow_read_reason,
  shadow.updated_at as shadow_read_updated_at,
  coalesce(dual_write.enabled, false) as dual_write_enabled,
  (
    select count(*)::integer
    from public.black_crown_ownership_migration_state as state
    where state.state = 'resolved'
  ) as resolved_mappings,
  (
    select count(*)::integer
    from public.black_crown_ownership_migration_state as state
    where state.state = 'unresolved'
  ) as unresolved_mappings,
  (
    select count(*)::integer
    from public.black_crown_ownership_migration_state as state
    where state.state = 'conflict'
  ) as conflict_mappings,
  (
    select count(*)::integer
    from public.black_crown_ownership_migration_state as state
    where state.state = 'merge_pending'
  ) as merge_pending_mappings
from public.black_crown_ownership_runtime_flags as shadow
left join public.black_crown_ownership_runtime_flags as dual_write
  on dual_write.flag_key = 'canonical_dual_write'
where shadow.flag_key = 'canonical_shadow_read';

revoke all on table public.black_crown_canonical_read_runtime_status
  from public, anon, authenticated;
grant select on table public.black_crown_canonical_read_runtime_status
  to service_role;

comment on view public.black_crown_canonical_read_runtime_status is
  'Service-role canonical shadow-read control and mapping readiness status.';
