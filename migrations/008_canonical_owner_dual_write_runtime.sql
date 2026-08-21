-- BLACK CROWN canonical ownership dual-write runtime (Phase 2B)
--
-- Legacy keys remain mandatory and continue to drive the current read path.
-- These triggers add a server-resolved black_crown_user_id projection to every
-- user-owned write. Browser/client supplied canonical IDs are ignored.
--
-- Rollback: set canonical_dual_write=false through the service-role RPC. Existing
-- canonical projections are preserved; new INSERTs remain legacy-only and UPDATEs
-- retain the previous canonical owner.

create table if not exists public.black_crown_ownership_runtime_flags (
  flag_key text primary key,
  enabled boolean not null,
  reason text not null,
  updated_at timestamptz not null default now(),
  constraint black_crown_ownership_runtime_flag_key_check
    check (flag_key in ('canonical_dual_write'))
);

insert into public.black_crown_ownership_runtime_flags (
  flag_key, enabled, reason, updated_at
) values (
  'canonical_dual_write', true, 'phase_2b_initial_enable', now()
)
on conflict (flag_key) do nothing;

alter table public.black_crown_ownership_runtime_flags enable row level security;
revoke all on table public.black_crown_ownership_runtime_flags
  from public, anon, authenticated;
grant select, update on table public.black_crown_ownership_runtime_flags
  to service_role;

do $policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'black_crown_ownership_runtime_flags'
      and policyname = 'black_crown_ownership_runtime_flags_browser_deny'
  ) then
    create policy black_crown_ownership_runtime_flags_browser_deny
      on public.black_crown_ownership_runtime_flags
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;
end
$policy$;

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
  if p_flag_key <> 'canonical_dual_write' then
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
    flag_key, enabled, reason, updated_at
  ) values (
    p_flag_key, coalesce(p_enabled, false), v_reason, now()
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

create or replace function public.black_crown_normalize_owner_candidates(
  p_candidates uuid[]
)
returns uuid[]
language sql
immutable
set search_path = pg_catalog, pg_temp
as $function$
  select coalesce(
    array_agg(distinct candidate order by candidate)
      filter (where candidate is not null),
    array[]::uuid[]
  )
  from unnest(coalesce(p_candidates, array[]::uuid[])) as valueset(candidate);
$function$;

revoke all on function public.black_crown_normalize_owner_candidates(uuid[])
  from public, anon, authenticated;
grant execute on function public.black_crown_normalize_owner_candidates(uuid[])
  to service_role;

create or replace function public.black_crown_eligible_identity_candidates(
  p_provider text,
  p_subject text
)
returns uuid[]
language sql
stable
security definer
set search_path = public, pg_temp
as $function$
  select coalesce(
    array_agg(distinct identity.black_crown_user_id order by identity.black_crown_user_id),
    array[]::uuid[]
  )
  from public.black_crown_identities as identity
  join public.black_crown_accounts as account
    on account.black_crown_user_id = identity.black_crown_user_id
  where nullif(trim(p_subject), '') is not null
    and identity.provider = p_provider
    and identity.provider_subject = p_subject
    and identity.status in ('active', 'provisional')
    and account.account_status in ('active', 'provisional');
$function$;

revoke all on function public.black_crown_eligible_identity_candidates(text, text)
  from public, anon, authenticated;
grant execute on function public.black_crown_eligible_identity_candidates(text, text)
  to service_role;

create or replace function public.black_crown_record_dual_write_state(
  p_scope text,
  p_provider text,
  p_subject text,
  p_state text,
  p_owner uuid,
  p_candidates uuid[],
  p_reason text,
  p_metadata jsonb default '{}'::jsonb
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_candidates uuid[] :=
    public.black_crown_normalize_owner_candidates(p_candidates);
  v_owner uuid := p_owner;
  v_state text := trim(coalesce(p_state, ''));
  v_scope text :=
    left(coalesce(nullif(trim(p_scope), ''), 'dual_write'), 128);
  v_provider text :=
    left(coalesce(nullif(trim(p_provider), ''), 'unknown'), 64);
  v_reason text := left(coalesce(p_reason, ''), 256);
  v_subject_hash text;
begin
  if nullif(trim(coalesce(p_subject, '')), '') is null then
    return;
  end if;
  if v_state not in ('resolved', 'unresolved', 'conflict', 'merge_pending') then
    raise exception using
      errcode = '22023',
      message = 'invalid canonical ownership migration state';
  end if;

  if v_state = 'resolved' then
    if v_owner is null
       or cardinality(v_candidates) <> 1
       or v_candidates[1] <> v_owner then
      raise exception using
        errcode = '22023',
        message = 'resolved canonical ownership state requires one matching owner';
    end if;
  else
    v_owner := null;
  end if;

  v_subject_hash :=
    public.black_crown_legacy_subject_hash(v_provider, p_subject);

  perform 1
  from public.black_crown_ownership_migration_state as current_state
  where current_state.scope = v_scope
    and current_state.legacy_provider = v_provider
    and current_state.legacy_subject_hash = v_subject_hash
    and current_state.state = v_state
    and current_state.black_crown_user_id is not distinct from v_owner
    and current_state.candidate_user_ids = v_candidates
    and current_state.last_reason = v_reason;

  if found then
    return;
  end if;

  insert into public.black_crown_ownership_migration_state as state (
    scope,
    legacy_provider,
    legacy_subject_hash,
    state,
    black_crown_user_id,
    candidate_user_ids,
    legacy_row_count,
    attempt_count,
    last_reason,
    metadata,
    first_seen_at,
    last_attempt_at,
    resolved_at
  ) values (
    v_scope,
    v_provider,
    v_subject_hash,
    v_state,
    v_owner,
    v_candidates,
    1,
    1,
    v_reason,
    jsonb_build_object(
      'authority', 'server_identity_projection',
      'dual_write', true,
      'raw_subject_stored', false,
      'client_owner_authority', false,
      'owner_overwrite_allowed', false,
      'silent_merge_allowed', false
    ) || coalesce(p_metadata, '{}'::jsonb),
    now(),
    now(),
    case when v_state = 'resolved' then now() else null end
  )
  on conflict (scope, legacy_provider, legacy_subject_hash)
  do update set
    state = excluded.state,
    black_crown_user_id = excluded.black_crown_user_id,
    candidate_user_ids = excluded.candidate_user_ids,
    legacy_row_count = greatest(state.legacy_row_count, 1),
    attempt_count = state.attempt_count + 1,
    last_reason = excluded.last_reason,
    metadata = excluded.metadata,
    last_attempt_at = now(),
    resolved_at = case
      when excluded.state = 'resolved' then coalesce(state.resolved_at, now())
      else null
    end;
end;
$function$;

revoke all on function public.black_crown_record_dual_write_state(
  text, text, text, text, uuid, uuid[], text, jsonb
) from public, anon, authenticated;
grant execute on function public.black_crown_record_dual_write_state(
  text, text, text, text, uuid, uuid[], text, jsonb
) to service_role;

create or replace function public.black_crown_record_owner_conflict_event(
  p_event_type text,
  p_provider text,
  p_subject text,
  p_scope text,
  p_candidates uuid[],
  p_reason text,
  p_metadata jsonb default '{}'::jsonb
)
returns void
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $function$
declare
  v_candidates uuid[] :=
    public.black_crown_normalize_owner_candidates(p_candidates);
  v_subject_hash text :=
    public.black_crown_legacy_subject_hash(p_provider, p_subject);
  v_fingerprint text;
begin
  v_fingerprint := encode(
    extensions.digest(
      coalesce(p_event_type, '') || ':' ||
      coalesce(p_scope, '') || ':' ||
      coalesce(array_to_string(v_candidates, ','), ''),
      'sha256'
    ),
    'hex'
  );

  insert into public.black_crown_identity_events (
    black_crown_user_id,
    event_type,
    provider,
    provider_subject_hash,
    metadata
  )
  select
    null,
    left(coalesce(nullif(trim(p_event_type), ''), 'canonical_owner_conflict'), 64),
    left(coalesce(nullif(trim(p_provider), ''), 'unknown'), 64),
    v_subject_hash,
    jsonb_build_object(
      'scope', left(coalesce(p_scope, ''), 128),
      'candidate_user_ids', v_candidates,
      'reason', left(coalesce(p_reason, ''), 256),
      'conflict_fingerprint', v_fingerprint,
      'raw_subject_stored', false,
      'client_owner_authority', false,
      'owner_overwrite_allowed', false,
      'silent_merge_allowed', false,
      'entitlement_transfer_allowed', false
    ) || coalesce(p_metadata, '{}'::jsonb)
  where not exists (
    select 1
    from public.black_crown_identity_events as event
    where event.event_type =
      left(coalesce(nullif(trim(p_event_type), ''), 'canonical_owner_conflict'), 64)
      and event.provider =
        left(coalesce(nullif(trim(p_provider), ''), 'unknown'), 64)
      and event.provider_subject_hash = v_subject_hash
      and event.metadata ->> 'conflict_fingerprint' = v_fingerprint
  );
end;
$function$;

revoke all on function public.black_crown_record_owner_conflict_event(
  text, text, text, text, uuid[], text, jsonb
) from public, anon, authenticated;
grant execute on function public.black_crown_record_owner_conflict_event(
  text, text, text, text, uuid[], text, jsonb
) to service_role;

create or replace function public.black_crown_apply_single_provider_owner()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_provider text;
  v_subject_column text;
  v_subject text;
  v_scope text;
  v_enabled boolean := false;
  v_old_owner uuid;
  v_owner uuid;
  v_resolved_owner uuid;
  v_candidates uuid[] := array[]::uuid[];
  v_state text;
  v_reason text;
begin
  if tg_nargs <> 3 then
    raise exception using
      errcode = '55000',
      message = 'canonical owner trigger configuration is invalid';
  end if;

  v_provider := tg_argv[0];
  v_subject_column := tg_argv[1];
  v_scope := tg_argv[2];

  select flags.enabled
  into v_enabled
  from public.black_crown_ownership_runtime_flags as flags
  where flags.flag_key = 'canonical_dual_write';

  if tg_op = 'UPDATE' then
    v_old_owner :=
      nullif(to_jsonb(old) ->> 'black_crown_user_id', '')::uuid;
  end if;

  if not coalesce(v_enabled, false) then
    new := jsonb_populate_record(
      new,
      jsonb_build_object(
        'black_crown_user_id',
        case when tg_op = 'UPDATE' then v_old_owner else null end
      )
    );
    return new;
  end if;

  v_subject := nullif(trim(to_jsonb(new) ->> v_subject_column), '');
  if v_subject is null then
    new := jsonb_populate_record(
      new,
      jsonb_build_object(
        'black_crown_user_id',
        case when tg_op = 'UPDATE' then v_old_owner else null end
      )
    );
    return new;
  end if;

  v_candidates :=
    public.black_crown_eligible_identity_candidates(v_provider, v_subject);

  if cardinality(v_candidates) = 1 then
    v_resolved_owner := v_candidates[1];
    if v_old_owner is null or v_old_owner = v_resolved_owner then
      v_owner := v_resolved_owner;
      v_state := 'resolved';
      v_reason := 'eligible_server_identity_resolved';
    else
      v_owner := v_old_owner;
      v_candidates := public.black_crown_normalize_owner_candidates(
        v_candidates || array[v_old_owner]::uuid[]
      );
      v_state := 'conflict';
      v_reason := 'existing_owner_differs_from_eligible_identity';
    end if;
  elsif cardinality(v_candidates) = 0 then
    v_owner := v_old_owner;
    v_state := 'unresolved';
    v_reason := 'eligible_server_identity_missing';
  else
    v_owner := v_old_owner;
    v_state := 'conflict';
    v_reason := 'multiple_eligible_identity_candidates';
  end if;

  new := jsonb_populate_record(
    new,
    jsonb_build_object('black_crown_user_id', v_owner)
  );

  perform public.black_crown_record_dual_write_state(
    v_scope,
    v_provider,
    v_subject,
    v_state,
    case when v_state = 'resolved' then v_owner else null end,
    v_candidates,
    v_reason,
    jsonb_build_object(
      'table', tg_table_name,
      'subject_column', v_subject_column
    )
  );

  if v_state = 'conflict' then
    perform public.black_crown_record_owner_conflict_event(
      'canonical_owner_conflict',
      v_provider,
      v_subject,
      v_scope,
      v_candidates,
      v_reason,
      jsonb_build_object('table', tg_table_name, 'operation', tg_op)
    );
  end if;

  return new;
end;
$function$;

revoke all on function public.black_crown_apply_single_provider_owner()
  from public, anon, authenticated;
grant execute on function public.black_crown_apply_single_provider_owner()
  to service_role;

create or replace function public.black_crown_apply_account_link_owner()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_scope text := 'account_link';
  v_enabled boolean := false;
  v_old_owner uuid;
  v_owner uuid;
  v_site_subject text;
  v_telegram_subject text;
  v_subject text;
  v_site_candidates uuid[] := array[]::uuid[];
  v_telegram_candidates uuid[] := array[]::uuid[];
  v_candidates uuid[] := array[]::uuid[];
  v_resolved_owner uuid;
  v_state text;
  v_reason text;
begin
  select flags.enabled
  into v_enabled
  from public.black_crown_ownership_runtime_flags as flags
  where flags.flag_key = 'canonical_dual_write';

  if tg_op = 'UPDATE' then
    v_old_owner :=
      nullif(to_jsonb(old) ->> 'black_crown_user_id', '')::uuid;
  end if;

  if not coalesce(v_enabled, false) then
    new := jsonb_populate_record(
      new,
      jsonb_build_object(
        'black_crown_user_id',
        case when tg_op = 'UPDATE' then v_old_owner else null end
      )
    );
    return new;
  end if;

  v_site_subject := nullif(trim(to_jsonb(new) ->> 'site_user_id'), '');
  v_telegram_subject := nullif(trim(to_jsonb(new) ->> 'telegram_user_id'), '');
  v_subject := coalesce(v_site_subject, '') || ':' ||
    coalesce(v_telegram_subject, '');

  v_site_candidates :=
    public.black_crown_eligible_identity_candidates(
      'website_auth', v_site_subject
    );
  v_telegram_candidates :=
    public.black_crown_eligible_identity_candidates(
      'telegram', v_telegram_subject
    );
  v_candidates := public.black_crown_normalize_owner_candidates(
    v_site_candidates || v_telegram_candidates
  );

  if v_site_subject is null or v_telegram_subject is null then
    v_owner := v_old_owner;
    v_state := 'unresolved';
    v_reason := 'linked_identity_subject_missing';
  elsif cardinality(v_site_candidates) = 1
     and cardinality(v_telegram_candidates) = 1
     and v_site_candidates[1] = v_telegram_candidates[1] then
    v_resolved_owner := v_site_candidates[1];
    if v_old_owner is null or v_old_owner = v_resolved_owner then
      v_owner := v_resolved_owner;
      v_state := 'resolved';
      v_reason := 'website_and_telegram_identities_agree';
    else
      v_owner := v_old_owner;
      v_candidates := public.black_crown_normalize_owner_candidates(
        v_candidates || array[v_old_owner]::uuid[]
      );
      v_state := 'conflict';
      v_reason := 'existing_link_owner_differs_from_identity_agreement';
    end if;
  elsif cardinality(v_site_candidates) = 1
     and cardinality(v_telegram_candidates) = 1
     and v_site_candidates[1] <> v_telegram_candidates[1] then
    v_owner := v_old_owner;
    v_state := 'merge_pending';
    v_reason := 'website_and_telegram_identities_disagree';
  elsif cardinality(v_site_candidates) > 1
     or cardinality(v_telegram_candidates) > 1 then
    v_owner := v_old_owner;
    v_state := 'conflict';
    v_reason := 'multiple_link_identity_candidates';
  else
    v_owner := v_old_owner;
    v_state := 'unresolved';
    v_reason := 'linked_identity_mapping_incomplete';
  end if;

  new := jsonb_populate_record(
    new,
    jsonb_build_object('black_crown_user_id', v_owner)
  );

  perform public.black_crown_record_dual_write_state(
    v_scope,
    'linked_identity',
    v_subject,
    v_state,
    case when v_state = 'resolved' then v_owner else null end,
    v_candidates,
    v_reason,
    jsonb_build_object(
      'table', tg_table_name,
      'entitlement_transfer_allowed', false
    )
  );

  if v_state in ('conflict', 'merge_pending') then
    perform public.black_crown_record_owner_conflict_event(
      case when v_state = 'merge_pending'
        then 'merge_pending'
        else 'canonical_owner_conflict'
      end,
      'linked_identity',
      v_subject,
      v_scope,
      v_candidates,
      v_reason,
      jsonb_build_object(
        'table', tg_table_name,
        'operation', tg_op,
        'entitlement_transfer_allowed', false
      )
    );
  end if;

  return new;
end;
$function$;

revoke all on function public.black_crown_apply_account_link_owner()
  from public, anon, authenticated;
grant execute on function public.black_crown_apply_account_link_owner()
  to service_role;

create or replace function public.black_crown_apply_account_link_event_owner()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_scope text := 'account_link_event';
  v_enabled boolean := false;
  v_old_owner uuid;
  v_owner uuid;
  v_site_subject text;
  v_telegram_subject text;
  v_subject text;
  v_site_candidates uuid[] := array[]::uuid[];
  v_telegram_candidates uuid[] := array[]::uuid[];
  v_candidates uuid[] := array[]::uuid[];
  v_resolved_owner uuid;
  v_state text;
  v_reason text;
begin
  select flags.enabled
  into v_enabled
  from public.black_crown_ownership_runtime_flags as flags
  where flags.flag_key = 'canonical_dual_write';

  if tg_op = 'UPDATE' then
    v_old_owner :=
      nullif(to_jsonb(old) ->> 'black_crown_user_id', '')::uuid;
  end if;

  if not coalesce(v_enabled, false) then
    new := jsonb_populate_record(
      new,
      jsonb_build_object(
        'black_crown_user_id',
        case when tg_op = 'UPDATE' then v_old_owner else null end
      )
    );
    return new;
  end if;

  v_site_subject := nullif(trim(to_jsonb(new) ->> 'site_user_id'), '');
  v_telegram_subject := nullif(trim(to_jsonb(new) ->> 'telegram_user_id'), '');
  v_subject := coalesce(v_site_subject, '') || ':' ||
    coalesce(v_telegram_subject, '');

  v_site_candidates :=
    public.black_crown_eligible_identity_candidates(
      'website_auth', v_site_subject
    );
  v_telegram_candidates :=
    public.black_crown_eligible_identity_candidates(
      'telegram', v_telegram_subject
    );
  v_candidates := public.black_crown_normalize_owner_candidates(
    v_site_candidates || v_telegram_candidates
  );

  if v_site_subject is not null and v_telegram_subject is not null then
    if cardinality(v_site_candidates) = 1
       and cardinality(v_telegram_candidates) = 1
       and v_site_candidates[1] = v_telegram_candidates[1] then
      v_resolved_owner := v_site_candidates[1];
      v_state := 'resolved';
      v_reason := 'event_identities_agree';
    elsif cardinality(v_site_candidates) = 1
       and cardinality(v_telegram_candidates) = 1
       and v_site_candidates[1] <> v_telegram_candidates[1] then
      v_state := 'merge_pending';
      v_reason := 'event_identities_disagree';
    elsif cardinality(v_site_candidates) > 1
       or cardinality(v_telegram_candidates) > 1 then
      v_state := 'conflict';
      v_reason := 'multiple_event_identity_candidates';
    else
      v_state := 'unresolved';
      v_reason := 'event_identity_mapping_incomplete';
    end if;
  elsif v_site_subject is not null then
    if cardinality(v_site_candidates) = 1 then
      v_resolved_owner := v_site_candidates[1];
      v_state := 'resolved';
      v_reason := 'event_website_identity_resolved';
    elsif cardinality(v_site_candidates) > 1 then
      v_state := 'conflict';
      v_reason := 'multiple_event_website_candidates';
    else
      v_state := 'unresolved';
      v_reason := 'event_website_identity_missing';
    end if;
  elsif v_telegram_subject is not null then
    if cardinality(v_telegram_candidates) = 1 then
      v_resolved_owner := v_telegram_candidates[1];
      v_state := 'resolved';
      v_reason := 'event_telegram_identity_resolved';
    elsif cardinality(v_telegram_candidates) > 1 then
      v_state := 'conflict';
      v_reason := 'multiple_event_telegram_candidates';
    else
      v_state := 'unresolved';
      v_reason := 'event_telegram_identity_missing';
    end if;
  else
    v_state := 'unresolved';
    v_reason := 'event_identity_subject_missing';
  end if;

  if v_state = 'resolved' then
    if v_old_owner is null or v_old_owner = v_resolved_owner then
      v_owner := v_resolved_owner;
    else
      v_owner := v_old_owner;
      v_candidates := public.black_crown_normalize_owner_candidates(
        v_candidates || array[v_old_owner]::uuid[]
      );
      v_state := 'conflict';
      v_reason := 'existing_event_owner_differs_from_identity';
    end if;
  else
    v_owner := v_old_owner;
  end if;

  new := jsonb_populate_record(
    new,
    jsonb_build_object('black_crown_user_id', v_owner)
  );

  perform public.black_crown_record_dual_write_state(
    v_scope,
    'linked_identity',
    v_subject,
    v_state,
    case when v_state = 'resolved' then v_owner else null end,
    v_candidates,
    v_reason,
    jsonb_build_object(
      'table', tg_table_name,
      'entitlement_transfer_allowed', false
    )
  );

  if v_state in ('conflict', 'merge_pending') then
    perform public.black_crown_record_owner_conflict_event(
      case when v_state = 'merge_pending'
        then 'merge_pending'
        else 'canonical_owner_conflict'
      end,
      'linked_identity',
      v_subject,
      v_scope,
      v_candidates,
      v_reason,
      jsonb_build_object(
        'table', tg_table_name,
        'operation', tg_op,
        'entitlement_transfer_allowed', false
      )
    );
  end if;

  return new;
end;
$function$;

revoke all on function public.black_crown_apply_account_link_event_owner()
  from public, anon, authenticated;
grant execute on function public.black_crown_apply_account_link_event_owner()
  to service_role;

do $triggers$
declare
  v_target record;
  v_trigger_name text;
begin
  for v_target in
    select *
    from (values
      ('bco_players', 'telegram', 'chat_id', 'product_state'),
      ('bco_messages', 'telegram', 'chat_id', 'product_state'),
      ('bco_episodes', 'telegram', 'chat_id', 'product_state'),
      ('bco_player_mistakes', 'telegram', 'chat_id', 'product_state'),
      ('bco_mistake_receipts', 'telegram', 'chat_id', 'product_state'),
      ('bco_progression_events', 'telegram', 'chat_id', 'product_state'),
      ('bco_training_sessions', 'telegram', 'chat_id', 'product_state'),
      ('bco_user_activity', 'telegram', 'telegram_user_id', 'analytics_activity'),
      ('blackcrown_entitlements', 'website_auth', 'site_user_id', 'entitlement')
    ) as targets(table_name, provider, subject_column, scope)
  loop
    v_trigger_name :=
      v_target.table_name || '_canonical_owner_dual_write';

    if not exists (
      select 1
      from pg_trigger
      where tgname = v_trigger_name
        and tgrelid =
          to_regclass(format('public.%I', v_target.table_name))
        and not tgisinternal
    ) then
      execute format(
        'create trigger %I before insert or update on public.%I for each row execute function public.black_crown_apply_single_provider_owner(%L, %L, %L)',
        v_trigger_name,
        v_target.table_name,
        v_target.provider,
        v_target.subject_column,
        v_target.scope
      );
    end if;
  end loop;

  if not exists (
    select 1
    from pg_trigger
    where tgname = 'blackcrown_account_links_canonical_owner_dual_write'
      and tgrelid = 'public.blackcrown_account_links'::regclass
      and not tgisinternal
  ) then
    create trigger blackcrown_account_links_canonical_owner_dual_write
      before insert or update
      on public.blackcrown_account_links
      for each row
      execute function public.black_crown_apply_account_link_owner();
  end if;

  if not exists (
    select 1
    from pg_trigger
    where tgname = 'blackcrown_account_link_events_canonical_owner_dual_write'
      and tgrelid = 'public.blackcrown_account_link_events'::regclass
      and not tgisinternal
  ) then
    create trigger blackcrown_account_link_events_canonical_owner_dual_write
      before insert or update
      on public.blackcrown_account_link_events
      for each row
      execute function public.black_crown_apply_account_link_event_owner();
  end if;
end
$triggers$;

create or replace view public.black_crown_ownership_runtime_status
with (security_invoker = true)
as
select
  'bco-canonical-owner-v2'::text as schema_version,
  coalesce(flags.enabled, false) as canonical_dual_write_enabled,
  flags.reason as canonical_dual_write_reason,
  flags.updated_at as canonical_dual_write_updated_at,
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
  ) as mapping_state
from public.black_crown_ownership_runtime_flags as flags
where flags.flag_key = 'canonical_dual_write';

revoke all on table public.black_crown_ownership_runtime_status
  from public, anon, authenticated;
grant select on table public.black_crown_ownership_runtime_status
  to service_role;

comment on table public.black_crown_ownership_runtime_flags is
  'Server-only operational rollback flags for canonical ownership migration.';
comment on view public.black_crown_ownership_runtime_status is
  'Service-role canonical dual-write readiness, trigger installation and coverage.';
