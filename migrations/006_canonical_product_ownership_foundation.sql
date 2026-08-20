-- BLACK CROWN canonical product ownership foundation (Phase 2A)
--
-- Additive migration only:
--   * legacy chat_id / telegram_user_id / site_user_id keys remain intact;
--   * black_crown_user_id is a nullable canonical projection during migration;
--   * existing non-null canonical owners are never overwritten;
--   * ambiguous identity mappings remain unowned;
--   * Website/Telegram disagreement becomes merge_pending and emits an audit event;
--   * no account, entitlement, Player Brain row, history row or identity is deleted;
--   * no raw legacy subject is stored in migration audit tables.
--
-- Safe rollback: disable future dual-read/dual-write flags. Do not drop additive
-- owner columns or audit records as an emergency rollback.

create table if not exists public.black_crown_ownership_migration_state (
  scope text not null,
  legacy_provider text not null,
  legacy_subject_hash text not null,
  state text not null,
  black_crown_user_id uuid null,
  candidate_user_ids uuid[] not null default array[]::uuid[],
  legacy_row_count bigint not null default 0,
  attempt_count integer not null default 0,
  last_reason text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_attempt_at timestamptz not null default now(),
  resolved_at timestamptz null,
  primary key (scope, legacy_provider, legacy_subject_hash),
  constraint black_crown_ownership_state_hash_check
    check (legacy_subject_hash ~ '^[0-9a-f]{64}$'),
  constraint black_crown_ownership_state_value_check
    check (state in ('resolved', 'unresolved', 'conflict', 'merge_pending')),
  constraint black_crown_ownership_state_rows_check
    check (legacy_row_count >= 0),
  constraint black_crown_ownership_state_attempts_check
    check (attempt_count >= 0),
  constraint black_crown_ownership_state_owner_check
    check (
      (
        state = 'resolved'
        and black_crown_user_id is not null
        and cardinality(candidate_user_ids) = 1
      )
      or
      (
        state <> 'resolved'
        and black_crown_user_id is null
      )
    ),
  constraint black_crown_ownership_state_account_fkey
    foreign key (black_crown_user_id)
    references public.black_crown_accounts (black_crown_user_id)
    on delete restrict
);

create index if not exists black_crown_ownership_state_status_idx
  on public.black_crown_ownership_migration_state (state, last_attempt_at desc);
create index if not exists black_crown_ownership_state_user_idx
  on public.black_crown_ownership_migration_state (black_crown_user_id)
  where black_crown_user_id is not null;

alter table public.black_crown_ownership_migration_state enable row level security;
revoke all on table public.black_crown_ownership_migration_state
  from public, anon, authenticated;
grant select, insert, update, delete
  on table public.black_crown_ownership_migration_state
  to service_role;

create table if not exists public.black_crown_ownership_migration_runs (
  run_id uuid primary key default extensions.gen_random_uuid(),
  schema_version text not null default 'bco-canonical-owner-v1',
  status text not null default 'running',
  batch_size integer not null,
  metrics jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz null,
  constraint black_crown_ownership_runs_status_check
    check (status in ('running', 'completed')),
  constraint black_crown_ownership_runs_batch_check
    check (batch_size between 1 and 50000)
);

create index if not exists black_crown_ownership_runs_started_idx
  on public.black_crown_ownership_migration_runs (started_at desc);

alter table public.black_crown_ownership_migration_runs enable row level security;
revoke all on table public.black_crown_ownership_migration_runs
  from public, anon, authenticated;
grant select, insert, update
  on table public.black_crown_ownership_migration_runs
  to service_role;

do $policies$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'black_crown_ownership_migration_state'
      and policyname = 'black_crown_ownership_state_browser_deny'
  ) then
    create policy black_crown_ownership_state_browser_deny
      on public.black_crown_ownership_migration_state
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'black_crown_ownership_migration_runs'
      and policyname = 'black_crown_ownership_runs_browser_deny'
  ) then
    create policy black_crown_ownership_runs_browser_deny
      on public.black_crown_ownership_migration_runs
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;
end
$policies$;

-- Add the canonical projection, FK and partial index to every current
-- user-owned product-state surface. Existing legacy keys are not modified.
do $ownership_ddl$
declare
  v_table text;
  v_constraint text;
  v_index text;
begin
  foreach v_table in array array[
    'bco_players',
    'bco_messages',
    'bco_episodes',
    'bco_player_mistakes',
    'bco_mistake_receipts',
    'bco_progression_events',
    'bco_training_sessions',
    'bco_user_activity',
    'blackcrown_account_links',
    'blackcrown_account_link_events',
    'blackcrown_entitlements'
  ]
  loop
    execute format(
      'alter table public.%I add column if not exists black_crown_user_id uuid null',
      v_table
    );

    v_constraint := v_table || '_black_crown_user_id_fkey';
    if not exists (
      select 1
      from pg_constraint as constraints
      where constraints.conname = v_constraint
        and constraints.conrelid = to_regclass(format('public.%I', v_table))
    ) then
      execute format(
        'alter table public.%I add constraint %I foreign key (black_crown_user_id) references public.black_crown_accounts (black_crown_user_id) on delete restrict not valid',
        v_table,
        v_constraint
      );
    end if;

    execute format(
      'alter table public.%I validate constraint %I',
      v_table,
      v_constraint
    );

    v_index := v_table || '_black_crown_user_id_idx';
    execute format(
      'create index if not exists %I on public.%I (black_crown_user_id) where black_crown_user_id is not null',
      v_index,
      v_table
    );
  end loop;
end
$ownership_ddl$;

-- Analytics is server-owned. It previously had no RLS.
alter table public.bco_user_activity enable row level security;
revoke all on table public.bco_user_activity from anon, authenticated;

do $activity_policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'bco_user_activity'
      and policyname = 'bco_user_activity_server_only'
  ) then
    create policy bco_user_activity_server_only
      on public.bco_user_activity
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;
end
$activity_policy$;

create or replace function public.black_crown_legacy_subject_hash(
  p_provider text,
  p_subject text
)
returns text
language sql
immutable
strict
set search_path = public, extensions
as $function$
  select encode(
    extensions.digest(
      convert_to(p_provider || ':' || p_subject, 'UTF8'),
      'sha256'
    ),
    'hex'
  );
$function$;

revoke all on function public.black_crown_legacy_subject_hash(text, text)
  from public, anon, authenticated;
grant execute on function public.black_crown_legacy_subject_hash(text, text)
  to service_role;

create or replace function public.black_crown_refresh_ownership_migration_state()
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $function$
declare
  v_metrics jsonb;
begin
  -- Product state, analytics and entitlements resolve only through active,
  -- server-owned identity records. Raw subjects exist only inside this query.
  with legacy_rows as (
    select 'product_state'::text as scope, 'telegram'::text as provider, chat_id::text as subject
      from public.bco_players
    union all select 'product_state', 'telegram', chat_id::text from public.bco_messages
    union all select 'product_state', 'telegram', chat_id::text from public.bco_episodes
    union all select 'product_state', 'telegram', chat_id::text from public.bco_player_mistakes
    union all select 'product_state', 'telegram', chat_id::text from public.bco_mistake_receipts
    union all select 'product_state', 'telegram', chat_id::text from public.bco_progression_events
    union all select 'product_state', 'telegram', chat_id::text from public.bco_training_sessions
    union all select 'analytics_activity', 'telegram', telegram_user_id::text from public.bco_user_activity
    union all select 'entitlement', 'website_auth', site_user_id from public.blackcrown_entitlements
  ), grouped as (
    select scope, provider, subject, count(*)::bigint as legacy_row_count
    from legacy_rows
    group by scope, provider, subject
  ), candidates as (
    select
      grouped.scope,
      grouped.provider,
      grouped.subject,
      grouped.legacy_row_count,
      coalesce(
        array_agg(
          distinct identities.black_crown_user_id
          order by identities.black_crown_user_id
        ) filter (where identities.black_crown_user_id is not null),
        array[]::uuid[]
      ) as candidate_user_ids
    from grouped
    left join public.black_crown_identities as identities
      on identities.provider = grouped.provider
     and identities.provider_subject = grouped.subject
     and identities.status = 'active'
    group by grouped.scope, grouped.provider, grouped.subject, grouped.legacy_row_count
  ), normalized as (
    select
      scope,
      provider,
      subject,
      legacy_row_count,
      candidate_user_ids,
      case cardinality(candidate_user_ids)
        when 0 then 'unresolved'
        when 1 then 'resolved'
        else 'conflict'
      end as state,
      case
        when cardinality(candidate_user_ids) = 1 then candidate_user_ids[1]
        else null
      end as owner_id,
      case cardinality(candidate_user_ids)
        when 0 then 'active_identity_missing'
        when 1 then 'active_identity_resolved'
        else 'multiple_active_identities'
      end as reason
    from candidates
  )
  insert into public.black_crown_ownership_migration_state as target (
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
  )
  select
    normalized.scope,
    normalized.provider,
    public.black_crown_legacy_subject_hash(normalized.provider, normalized.subject),
    normalized.state,
    normalized.owner_id,
    normalized.candidate_user_ids,
    normalized.legacy_row_count,
    1,
    normalized.reason,
    jsonb_build_object(
      'authority', 'active_server_identity',
      'raw_subject_stored', false,
      'silent_merge_allowed', false
    ),
    now(),
    now(),
    case when normalized.state = 'resolved' then now() else null end
  from normalized
  on conflict (scope, legacy_provider, legacy_subject_hash)
  do update set
    state = excluded.state,
    black_crown_user_id = excluded.black_crown_user_id,
    candidate_user_ids = excluded.candidate_user_ids,
    legacy_row_count = excluded.legacy_row_count,
    attempt_count = target.attempt_count + 1,
    last_reason = excluded.last_reason,
    metadata = excluded.metadata,
    last_attempt_at = now(),
    resolved_at = case
      when excluded.state = 'resolved' then coalesce(target.resolved_at, now())
      else null
    end;

  -- Linked Website and Telegram identities must both exist and agree. A
  -- disagreement is merge_pending; Premium and product state are not moved.
  with mapped as (
    select
      links.site_user_id,
      links.telegram_user_id,
      website_identity.black_crown_user_id as website_owner,
      telegram_identity.black_crown_user_id as telegram_owner
    from public.blackcrown_account_links as links
    left join public.black_crown_identities as website_identity
      on website_identity.provider = 'website_auth'
     and website_identity.provider_subject = links.site_user_id
     and website_identity.status = 'active'
    left join public.black_crown_identities as telegram_identity
      on telegram_identity.provider = 'telegram'
     and telegram_identity.provider_subject = links.telegram_user_id::text
     and telegram_identity.status = 'active'
  ), normalized as (
    select
      site_user_id,
      telegram_user_id,
      website_owner,
      telegram_owner,
      array(
        select distinct owner_id
        from unnest(array[website_owner, telegram_owner]::uuid[]) as owners(owner_id)
        where owner_id is not null
        order by owner_id
      ) as candidate_user_ids,
      case
        when website_owner is not null and website_owner = telegram_owner then 'resolved'
        when website_owner is not null and telegram_owner is not null and website_owner <> telegram_owner then 'merge_pending'
        else 'unresolved'
      end as state,
      case
        when website_owner is not null and website_owner = telegram_owner then website_owner
        else null
      end as owner_id,
      case
        when website_owner is not null and website_owner = telegram_owner then 'linked_identities_agree'
        when website_owner is not null and telegram_owner is not null and website_owner <> telegram_owner then 'canonical_identity_conflict'
        when website_owner is null and telegram_owner is null then 'linked_identities_missing'
        when website_owner is null then 'website_identity_missing'
        else 'telegram_identity_missing'
      end as reason
    from mapped
  )
  insert into public.black_crown_ownership_migration_state as target (
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
  )
  select
    'account_link',
    'linked_identity',
    public.black_crown_legacy_subject_hash(
      'linked_identity',
      normalized.site_user_id || ':' || normalized.telegram_user_id::text
    ),
    normalized.state,
    normalized.owner_id,
    normalized.candidate_user_ids,
    1,
    1,
    normalized.reason,
    jsonb_build_object(
      'authority', 'website_and_telegram_identity_agreement',
      'raw_subject_stored', false,
      'silent_merge_allowed', false,
      'entitlement_transfer_allowed', false
    ),
    now(),
    now(),
    case when normalized.state = 'resolved' then now() else null end
  from normalized
  on conflict (scope, legacy_provider, legacy_subject_hash)
  do update set
    state = excluded.state,
    black_crown_user_id = excluded.black_crown_user_id,
    candidate_user_ids = excluded.candidate_user_ids,
    legacy_row_count = excluded.legacy_row_count,
    attempt_count = target.attempt_count + 1,
    last_reason = excluded.last_reason,
    metadata = excluded.metadata,
    last_attempt_at = now(),
    resolved_at = case
      when excluded.state = 'resolved' then coalesce(target.resolved_at, now())
      else null
    end;

  insert into public.black_crown_identity_events (
    black_crown_user_id,
    event_type,
    provider,
    provider_subject_hash,
    metadata
  )
  select
    null,
    'merge_pending',
    'linked_identity',
    state.legacy_subject_hash,
    jsonb_build_object(
      'scope', state.scope,
      'candidate_user_ids', state.candidate_user_ids,
      'reason', state.last_reason,
      'silent_merge_allowed', false,
      'entitlement_transfer_allowed', false,
      'raw_subject_stored', false
    )
  from public.black_crown_ownership_migration_state as state
  where state.scope = 'account_link'
    and state.state = 'merge_pending'
    and not exists (
      select 1
      from public.black_crown_identity_events as events
      where events.event_type = 'merge_pending'
        and events.provider = 'linked_identity'
        and events.provider_subject_hash = state.legacy_subject_hash
    );

  select jsonb_build_object(
    'resolved', count(*) filter (where state = 'resolved'),
    'unresolved', count(*) filter (where state = 'unresolved'),
    'conflict', count(*) filter (where state = 'conflict'),
    'merge_pending', count(*) filter (where state = 'merge_pending')
  )
  into v_metrics
  from public.black_crown_ownership_migration_state;

  return coalesce(v_metrics, '{}'::jsonb);
end;
$function$;

revoke all on function public.black_crown_refresh_ownership_migration_state()
  from public, anon, authenticated;
grant execute on function public.black_crown_refresh_ownership_migration_state()
  to service_role;

create or replace view public.black_crown_ownership_coverage
with (security_invoker = true)
as
  select
    'bco_players'::text as table_name,
    count(*)::bigint as total_rows,
    count(black_crown_user_id)::bigint as canonical_rows,
    count(*) filter (where black_crown_user_id is null)::bigint as legacy_only_rows,
    case when count(*) = 0 then 100.00
      else round(100.0 * count(black_crown_user_id) / count(*), 2)
    end as coverage_percent
  from public.bco_players
  union all
  select 'bco_messages', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_messages
  union all
  select 'bco_episodes', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_episodes
  union all
  select 'bco_player_mistakes', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_player_mistakes
  union all
  select 'bco_mistake_receipts', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_mistake_receipts
  union all
  select 'bco_progression_events', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_progression_events
  union all
  select 'bco_training_sessions', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_training_sessions
  union all
  select 'bco_user_activity', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.bco_user_activity
  union all
  select 'blackcrown_account_links', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.blackcrown_account_links
  union all
  select 'blackcrown_account_link_events', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.blackcrown_account_link_events
  union all
  select 'blackcrown_entitlements', count(*), count(black_crown_user_id),
    count(*) filter (where black_crown_user_id is null),
    case when count(*) = 0 then 100.00 else round(100.0 * count(black_crown_user_id) / count(*), 2) end
  from public.blackcrown_entitlements;

revoke all on table public.black_crown_ownership_coverage
  from public, anon, authenticated;
grant select on table public.black_crown_ownership_coverage to service_role;

create or replace function public.black_crown_backfill_product_ownership(
  p_batch_size integer default 5000
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $function$
declare
  v_batch_size integer := greatest(1, least(coalesce(p_batch_size, 5000), 50000));
  v_run_id uuid := extensions.gen_random_uuid();
  v_target record;
  v_updated integer;
  v_updates jsonb := '{}'::jsonb;
  v_mapping_state jsonb;
  v_coverage jsonb;
begin
  insert into public.black_crown_ownership_migration_runs (
    run_id,
    status,
    batch_size,
    metrics
  ) values (
    v_run_id,
    'running',
    v_batch_size,
    '{}'::jsonb
  );

  -- Simple one-provider mappings. The provider and table/column identifiers are
  -- hard-coded server migration metadata, never browser input.
  for v_target in
    select *
    from (values
      ('bco_players', 'chat_id', 'telegram'),
      ('bco_messages', 'chat_id', 'telegram'),
      ('bco_episodes', 'chat_id', 'telegram'),
      ('bco_player_mistakes', 'chat_id', 'telegram'),
      ('bco_mistake_receipts', 'chat_id', 'telegram'),
      ('bco_progression_events', 'chat_id', 'telegram'),
      ('bco_training_sessions', 'chat_id', 'telegram'),
      ('bco_user_activity', 'telegram_user_id', 'telegram'),
      ('blackcrown_entitlements', 'site_user_id', 'website_auth')
    ) as targets(table_name, subject_column, provider)
  loop
    execute format(
      $sql$
        with candidates as (
          select target.ctid as row_id, identity.black_crown_user_id
          from public.%I as target
          join public.black_crown_identities as identity
            on identity.provider = %L
           and identity.provider_subject = target.%I::text
           and identity.status = 'active'
          where target.black_crown_user_id is null
          order by target.%I::text
          limit $1
        )
        update public.%I as target
        set black_crown_user_id = candidates.black_crown_user_id
        from candidates
        where target.ctid = candidates.row_id
          and target.black_crown_user_id is null
      $sql$,
      v_target.table_name,
      v_target.provider,
      v_target.subject_column,
      v_target.subject_column,
      v_target.table_name
    ) using v_batch_size;

    get diagnostics v_updated = row_count;
    v_updates := v_updates || jsonb_build_object(v_target.table_name, v_updated);
  end loop;

  -- Account links resolve only when verified Website and Telegram identities
  -- agree on one canonical user. Conflicts remain null and become merge_pending.
  with candidates as (
    select links.ctid as row_id, telegram_identity.black_crown_user_id
    from public.blackcrown_account_links as links
    join public.black_crown_identities as website_identity
      on website_identity.provider = 'website_auth'
     and website_identity.provider_subject = links.site_user_id
     and website_identity.status = 'active'
    join public.black_crown_identities as telegram_identity
      on telegram_identity.provider = 'telegram'
     and telegram_identity.provider_subject = links.telegram_user_id::text
     and telegram_identity.status = 'active'
     and telegram_identity.black_crown_user_id = website_identity.black_crown_user_id
    where links.black_crown_user_id is null
    order by links.site_user_id, links.telegram_user_id
    limit v_batch_size
  )
  update public.blackcrown_account_links as links
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where links.ctid = candidates.row_id
    and links.black_crown_user_id is null;

  get diagnostics v_updated = row_count;
  v_updates := v_updates || jsonb_build_object('blackcrown_account_links', v_updated);

  -- Audit events can resolve from one supplied identity. If both are present,
  -- both must resolve and agree.
  with mapped as (
    select
      events.ctid as row_id,
      events.site_user_id,
      events.telegram_user_id,
      website_identity.black_crown_user_id as website_owner,
      telegram_identity.black_crown_user_id as telegram_owner
    from public.blackcrown_account_link_events as events
    left join public.black_crown_identities as website_identity
      on website_identity.provider = 'website_auth'
     and website_identity.provider_subject = events.site_user_id
     and website_identity.status = 'active'
    left join public.black_crown_identities as telegram_identity
      on telegram_identity.provider = 'telegram'
     and telegram_identity.provider_subject = events.telegram_user_id::text
     and telegram_identity.status = 'active'
    where events.black_crown_user_id is null
  ), candidates as (
    select row_id, coalesce(website_owner, telegram_owner) as black_crown_user_id
    from mapped
    where coalesce(website_owner, telegram_owner) is not null
      and (site_user_id is null or website_owner is not null)
      and (telegram_user_id is null or telegram_owner is not null)
      and (
        website_owner is null
        or telegram_owner is null
        or website_owner = telegram_owner
      )
    order by row_id
    limit v_batch_size
  )
  update public.blackcrown_account_link_events as events
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where events.ctid = candidates.row_id
    and events.black_crown_user_id is null;

  get diagnostics v_updated = row_count;
  v_updates := v_updates || jsonb_build_object('blackcrown_account_link_events', v_updated);

  select public.black_crown_refresh_ownership_migration_state()
    into v_mapping_state;

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
  into v_coverage
  from public.black_crown_ownership_coverage as coverage;

  update public.black_crown_ownership_migration_runs as runs
  set
    status = 'completed',
    metrics = jsonb_build_object(
      'updated_rows', v_updates,
      'mapping_state', v_mapping_state,
      'coverage', v_coverage
    ),
    completed_at = now()
  where runs.run_id = v_run_id;

  return jsonb_build_object(
    'ok', true,
    'run_id', v_run_id,
    'schema_version', 'bco-canonical-owner-v1',
    'batch_size', v_batch_size,
    'updated_rows', v_updates,
    'mapping_state', v_mapping_state,
    'coverage', v_coverage
  );
end;
$function$;

revoke all on function public.black_crown_backfill_product_ownership(integer)
  from public, anon, authenticated;
grant execute on function public.black_crown_backfill_product_ownership(integer)
  to service_role;

comment on function public.black_crown_backfill_product_ownership(integer) is
  'Idempotent and resumable canonical owner projection. Never creates or merges accounts and never overwrites a non-null owner.';
comment on view public.black_crown_ownership_coverage is
  'Privacy-safe canonical ownership coverage. Raw identity subjects are not exposed.';

-- Initial bounded pass. Re-running is safe: only rows with a null canonical
-- projection are considered, and conflicting linked identities remain null.
select public.black_crown_backfill_product_ownership(50000);
