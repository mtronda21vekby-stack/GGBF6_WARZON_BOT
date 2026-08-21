-- BLACK CROWN canonical lifecycle runtime (Phase 2D)
--
-- Staged, additive lifecycle semantics for clear/reset/purge operations.
-- The application never supplies black_crown_user_id. GAME resolves the trusted
-- Telegram provider subject server-side and applies canonical scope only when
-- the independent canonical_lifecycle flag is enabled and exactly one eligible
-- account exists. Disabled, unresolved and conflicting states retain the exact
-- legacy-subject behavior. Accounts, identities, links and entitlements are
-- never deleted by these functions.

alter table public.black_crown_ownership_runtime_flags
  drop constraint if exists black_crown_ownership_runtime_flag_key_check;

alter table public.black_crown_ownership_runtime_flags
  add constraint black_crown_ownership_runtime_flag_key_check
  check (
    flag_key in (
      'canonical_dual_write',
      'canonical_shadow_read',
      'canonical_lifecycle'
    )
  );

insert into public.black_crown_ownership_runtime_flags (
  flag_key,
  enabled,
  reason,
  updated_at
) values (
  'canonical_lifecycle',
  false,
  'phase_2d_staged_disabled',
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
  if p_flag_key not in (
    'canonical_dual_write',
    'canonical_shadow_read',
    'canonical_lifecycle'
  ) then
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

create or replace function public.black_crown_resolve_lifecycle_scope(
  p_telegram_user_id bigint
)
returns table (
  lifecycle_enabled boolean,
  resolution_state text,
  black_crown_user_id uuid,
  telegram_user_ids bigint[]
)
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_candidates uuid[] := array[]::uuid[];
  v_owner uuid;
  v_linked_subjects bigint[] := array[]::bigint[];
begin
  if p_telegram_user_id is null or p_telegram_user_id <= 0 then
    raise exception using
      errcode = '22023',
      message = 'valid Telegram user ID is required';
  end if;

  telegram_user_ids := array[p_telegram_user_id]::bigint[];

  select coalesce(flags.enabled, false)
  into lifecycle_enabled
  from public.black_crown_ownership_runtime_flags as flags
  where flags.flag_key = 'canonical_lifecycle';

  lifecycle_enabled := coalesce(lifecycle_enabled, false);
  v_candidates := public.black_crown_eligible_identity_candidates(
    'telegram',
    p_telegram_user_id::text
  );

  resolution_state := case cardinality(v_candidates)
    when 0 then 'unresolved'
    when 1 then 'resolved'
    else 'conflict'
  end;

  if cardinality(v_candidates) = 1 then
    v_owner := v_candidates[1];
    black_crown_user_id := v_owner;

    select coalesce(
      array_agg(
        distinct identity.provider_subject::bigint
        order by identity.provider_subject::bigint
      ),
      array[]::bigint[]
    )
    into v_linked_subjects
    from public.black_crown_identities as identity
    join public.black_crown_accounts as account
      on account.black_crown_user_id = identity.black_crown_user_id
    where identity.black_crown_user_id = v_owner
      and identity.provider = 'telegram'
      and identity.status in ('active', 'provisional')
      and account.account_status in ('active', 'provisional')
      and identity.provider_subject ~ '^[1-9][0-9]{0,17}$';

    select coalesce(
      array_agg(distinct subject order by subject),
      array[p_telegram_user_id]::bigint[]
    )
    into telegram_user_ids
    from unnest(
      coalesce(v_linked_subjects, array[]::bigint[])
      || array[p_telegram_user_id]::bigint[]
    ) as linked(subject);
  else
    black_crown_user_id := null;
  end if;

  return next;
end;
$function$;

revoke all on function public.black_crown_resolve_lifecycle_scope(bigint)
  from public, anon, authenticated;
grant execute on function public.black_crown_resolve_lifecycle_scope(bigint)
  to service_role;

create or replace function public.black_crown_clear_conversation(
  p_telegram_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_scope record;
  v_canonical_scope boolean := false;
  v_deleted integer := 0;
begin
  select *
  into v_scope
  from public.black_crown_resolve_lifecycle_scope(p_telegram_user_id);

  v_canonical_scope :=
    coalesce(v_scope.lifecycle_enabled, false)
    and v_scope.resolution_state = 'resolved'
    and v_scope.black_crown_user_id is not null;

  if v_canonical_scope then
    delete from public.bco_messages
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_messages
    where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;

  return jsonb_build_object(
    'ok', true,
    'schema_version', 'bco-canonical-lifecycle-v1',
    'operation', 'clear_conversation',
    'mode', case when v_canonical_scope then 'canonical_account' else 'legacy_subject' end,
    'resolution_state', v_scope.resolution_state,
    'canonical_scope_applied', v_canonical_scope,
    'legacy_fallback_applied', not v_canonical_scope,
    'linked_telegram_subject_count', cardinality(v_scope.telegram_user_ids),
    'deleted_rows', v_deleted
  );
end;
$function$;

create or replace function public.black_crown_reset_player_profile(
  p_telegram_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_scope record;
  v_canonical_scope boolean := false;
  v_deleted integer := 0;
begin
  select *
  into v_scope
  from public.black_crown_resolve_lifecycle_scope(p_telegram_user_id);

  v_canonical_scope :=
    coalesce(v_scope.lifecycle_enabled, false)
    and v_scope.resolution_state = 'resolved'
    and v_scope.black_crown_user_id is not null;

  if v_canonical_scope then
    delete from public.bco_players
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_players
    where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;

  return jsonb_build_object(
    'ok', true,
    'schema_version', 'bco-canonical-lifecycle-v1',
    'operation', 'reset_profile',
    'mode', case when v_canonical_scope then 'canonical_account' else 'legacy_subject' end,
    'resolution_state', v_scope.resolution_state,
    'canonical_scope_applied', v_canonical_scope,
    'legacy_fallback_applied', not v_canonical_scope,
    'linked_telegram_subject_count', cardinality(v_scope.telegram_user_ids),
    'deleted_rows', v_deleted
  );
end;
$function$;

create or replace function public.black_crown_purge_product_data(
  p_telegram_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_scope record;
  v_canonical_scope boolean := false;
  v_deleted integer := 0;
  v_deleted_rows jsonb := '{}'::jsonb;
begin
  select *
  into v_scope
  from public.black_crown_resolve_lifecycle_scope(p_telegram_user_id);

  v_canonical_scope :=
    coalesce(v_scope.lifecycle_enabled, false)
    and v_scope.resolution_state = 'resolved'
    and v_scope.black_crown_user_id is not null;

  if v_canonical_scope then
    delete from public.bco_messages
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_messages where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('messages', v_deleted);

  if v_canonical_scope then
    delete from public.bco_player_mistakes
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_player_mistakes where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('mistakes', v_deleted);

  if v_canonical_scope then
    delete from public.bco_mistake_receipts
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_mistake_receipts where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('mistake_receipts', v_deleted);

  if v_canonical_scope then
    delete from public.bco_episodes
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_episodes where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('episodes', v_deleted);

  if v_canonical_scope then
    delete from public.bco_training_sessions
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_training_sessions where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('training_sessions', v_deleted);

  if v_canonical_scope then
    delete from public.bco_progression_events
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_progression_events where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('progression_events', v_deleted);

  if v_canonical_scope then
    delete from public.bco_user_activity
    where black_crown_user_id = v_scope.black_crown_user_id
       or telegram_user_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_user_activity
    where telegram_user_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('analytics_activity', v_deleted);

  if v_canonical_scope then
    delete from public.bco_players
    where black_crown_user_id = v_scope.black_crown_user_id
       or chat_id = any(v_scope.telegram_user_ids);
  else
    delete from public.bco_players where chat_id = p_telegram_user_id;
  end if;
  get diagnostics v_deleted = row_count;
  v_deleted_rows := v_deleted_rows || jsonb_build_object('players', v_deleted);

  return jsonb_build_object(
    'ok', true,
    'schema_version', 'bco-canonical-lifecycle-v1',
    'operation', 'purge_product_data',
    'mode', case when v_canonical_scope then 'canonical_account' else 'legacy_subject' end,
    'resolution_state', v_scope.resolution_state,
    'canonical_scope_applied', v_canonical_scope,
    'legacy_fallback_applied', not v_canonical_scope,
    'linked_telegram_subject_count', cardinality(v_scope.telegram_user_ids),
    'deleted_rows', v_deleted_rows,
    'account_preserved', true,
    'identities_preserved', true,
    'entitlements_preserved', true
  );
end;
$function$;

revoke all on function public.black_crown_clear_conversation(bigint)
  from public, anon, authenticated;
revoke all on function public.black_crown_reset_player_profile(bigint)
  from public, anon, authenticated;
revoke all on function public.black_crown_purge_product_data(bigint)
  from public, anon, authenticated;
grant execute on function public.black_crown_clear_conversation(bigint)
  to service_role;
grant execute on function public.black_crown_reset_player_profile(bigint)
  to service_role;
grant execute on function public.black_crown_purge_product_data(bigint)
  to service_role;

create or replace view public.black_crown_lifecycle_runtime_status
with (security_invoker = true)
as
select
  'bco-canonical-lifecycle-v1'::text as schema_version,
  lifecycle.enabled as lifecycle_enabled,
  lifecycle.reason as lifecycle_reason,
  lifecycle.updated_at as lifecycle_updated_at,
  coalesce(dual_write.enabled, false) as dual_write_enabled,
  coalesce(shadow.enabled, false) as shadow_read_enabled,
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
  ) as merge_pending_mappings,
  true as legacy_fallback_available,
  false as account_deletion_enabled,
  false as identity_deletion_enabled,
  false as entitlement_deletion_enabled
from public.black_crown_ownership_runtime_flags as lifecycle
left join public.black_crown_ownership_runtime_flags as dual_write
  on dual_write.flag_key = 'canonical_dual_write'
left join public.black_crown_ownership_runtime_flags as shadow
  on shadow.flag_key = 'canonical_shadow_read'
where lifecycle.flag_key = 'canonical_lifecycle';

revoke all on table public.black_crown_lifecycle_runtime_status
  from public, anon, authenticated;
grant select on table public.black_crown_lifecycle_runtime_status
  to service_role;

comment on function public.black_crown_clear_conversation(bigint) is
  'Clears conversation data in exact legacy scope or every server-owned Telegram subject of one resolved canonical account.';
comment on function public.black_crown_reset_player_profile(bigint) is
  'Resets profile/summary/derived state in exact legacy scope or every server-owned Telegram subject of one resolved canonical account.';
comment on function public.black_crown_purge_product_data(bigint) is
  'Purges BLACK CROWN product data across one resolved canonical account while preserving account, identity, links and entitlements.';
comment on view public.black_crown_lifecycle_runtime_status is
  'Privacy-safe service-role lifecycle control and migration readiness status.';
