-- BLACK CROWN canonical product ownership foundation
--
-- Phase 2A is intentionally additive:
--   * legacy chat/site keys remain intact and authoritative for the current runtime;
--   * nullable black_crown_user_id projections are added for dual-read/dual-write rollout;
--   * no account is merged, no legacy row is deleted, and no owner column is made NOT NULL;
--   * ambiguous mappings remain unowned and are recorded as conflict/merge_pending;
--   * raw legacy subjects are never copied into the migration-state ledger.
--
-- Rollback contract: disable future dual-write/read flags and leave these additive
-- columns/ledger rows in place. Dropping owner columns is not a safe rollback.

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
      (state = 'resolved'
        and black_crown_user_id is not null
        and cardinality(candidate_user_ids) = 1)
      or
      (state <> 'resolved' and black_crown_user_id is null)
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
revoke all on table public.black_crown_ownership_migration_state from public, anon, authenticated;
grant select, insert, update, delete on table public.black_crown_ownership_migration_state to service_role;

do $policy$
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
end
$policy$;

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
revoke all on table public.black_crown_ownership_migration_runs from public, anon, authenticated;
grant select, insert, update on table public.black_crown_ownership_migration_runs to service_role;

do $policy$
begin
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
$policy$;

alter table public.bco_players
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_messages
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_episodes
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_player_mistakes
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_mistake_receipts
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_progression_events
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_training_sessions
  add column if not exists black_crown_user_id uuid null;
alter table public.bco_user_activity
  add column if not exists black_crown_user_id uuid null;
alter table public.blackcrown_account_links
  add column if not exists black_crown_user_id uuid null;
alter table public.blackcrown_account_link_events
  add column if not exists black_crown_user_id uuid null;
alter table public.blackcrown_entitlements
  add column if not exists black_crown_user_id uuid null;

-- Add owner FKs as NOT VALID first to avoid a long blocking validation scan on
-- larger future installations. Validation is then explicit and idempotent.
do $constraints$
declare
  item record;
  constraint_name text;
begin
  for item in
    select table_name
    from (values
      ('bco_players'),
      ('bco_messages'),
      ('bco_episodes'),
      ('bco_player_mistakes'),
      ('bco_mistake_receipts'),
      ('bco_progression_events'),
      ('bco_training_sessions'),
      ('bco_user_activity'),
      ('blackcrown_account_links'),
      ('blackcrown_account_link_events'),
      ('blackcrown_entitlements')
    ) as tables(table_name)
  loop
    constraint_name := item.table_name || '_black_crown_user_id_fkey';
    if not exists (
      select 1
      from pg_constraint
      where conname = constraint_name
        and conrelid = to_regclass(format('public.%I', item.table_name))
    ) then
      execute format(
        'alter table public.%I add constraint %I foreign key (black_crown_user_id) references public.black_crown_accounts (black_crown_user_id) on delete restrict not valid',
        item.table_name,
        constraint_name
      );
    end if;
    execute format(
      'alter table public.%I validate constraint %I',
      item.table_name,
      constraint_name
    );
  end loop;
end
$constraints$;

create index if not exists bco_players_black_crown_user_idx
  on public.bco_players (black_crown_user_id)
  where black_crown_user_id is not null;
create index if not exists bco_messages_black_crown_user_id_idx
  on public.bco_messages (black_crown_user_id, id desc)
  where black_crown_user_id is not null;
create index if not exists bco_episodes_black_crown_user_id_idx
  on public.bco_episodes (black_crown_user_id, id desc)
  where black_crown_user_id is not null;
create index if not exists bco_player_mistakes_black_crown_user_idx
  on public.bco_player_mistakes (black_crown_user_id, count desc, last_seen desc)
  where black_crown_user_id is not null;
create index if not exists bco_mistake_receipts_black_crown_user_idx
  on public.bco_mistake_receipts (black_crown_user_id, created_at desc)
  where black_crown_user_id is not null;
create index if not exists bco_progression_events_black_crown_user_idx
  on public.bco_progression_events (black_crown_user_id, id desc)
  where black_crown_user_id is not null;
create index if not exists bco_training_sessions_black_crown_user_idx
  on public.bco_training_sessions (black_crown_user_id, id desc)
  where black_crown_user_id is not null;
create index if not exists bco_user_activity_black_crown_user_idx
  on public.bco_user_activity (black_crown_user_id, last_seen_at desc)
  where black_crown_user_id is not null;
create index if not exists blackcrown_account_links_black_crown_user_idx
  on public.blackcrown_account_links (black_crown_user_id)
  where black_crown_user_id is not null;
create index if not exists blackcrown_account_link_events_black_crown_user_idx
  on public.blackcrown_account_link_events (black_crown_user_id, id desc)
  where black_crown_user_id is not null;
create index if not exists blackcrown_entitlements_black_crown_user_active_idx
  on public.blackcrown_entitlements (black_crown_user_id, entitlement_key, valid_until)
  where black_crown_user_id is not null and status = 'active';

-- Analytics is server-owned. RLS was historically absent on this table.
alter table public.bco_user_activity enable row level security;
revoke all on table public.bco_user_activity from anon, authenticated;

do $policy$
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
$policy$;

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
  result jsonb;
begin
  -- Persistent product state still keyed by chat_id.
  with legacy_rows as (
    select chat_id::text as legacy_subject from public.bco_players
    union all select chat_id::text from public.bco_messages
    union all select chat_id::text from public.bco_episodes
    union all select chat_id::text from public.bco_player_mistakes
    union all select chat_id::text from public.bco_mistake_receipts
    union all select chat_id::text from public.bco_progression_events
    union all select chat_id::text from public.bco_training_sessions
  ), subjects as (
    select legacy_subject, count(*)::bigint as legacy_row_count
    from legacy_rows
    group by legacy_subject
  ), candidates as (
    select
      subjects.legacy_subject,
      subjects.legacy_row_count,
      coalesce(
        array_agg(distinct identities.black_crown_user_id order by identities.black_crown_user_id)
          filter (where identities.black_crown_user_id is not null),
        array[]::uuid[]
      ) as candidate_user_ids
    from subjects
    left join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = subjects.legacy_subject
     and identities.status = 'active'
    group by subjects.legacy_subject, subjects.legacy_row_count
  ), normalized as (
    select
      legacy_subject,
      legacy_row_count,
      candidate_user_ids,
      case cardinality(candidate_user_ids)
        when 0 then 'unresolved'
        when 1 then 'resolved'
        else 'conflict'
      end as state,
      case when cardinality(candidate_user_ids) = 1 then candidate_user_ids[1] else null end as owner_id,
      case cardinality(candidate_user_ids)
        when 0 then 'active_telegram_identity_missing'
        when 1 then 'active_telegram_identity_resolved'
        else 'multiple_active_telegram_identities'
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
    'product_state',
    'telegram',
    public.black_crown_legacy_subject_hash('telegram', legacy_subject),
    state,
    owner_id,
    candidate_user_ids,
    legacy_row_count,
    1,
    reason,
    jsonb_build_object(
      'authority', 'active_telegram_identity',
      'raw_subject_stored', false
    ),
    now(),
    now(),
    case when state = 'resolved' then now() else null end
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

  -- Analytics currently keys activity by Telegram user ID rather than chat ID.
  with subjects as (
    select telegram_user_id::text as legacy_subject, count(*)::bigint as legacy_row_count
    from public.bco_user_activity
    group by telegram_user_id
  ), candidates as (
    select
      subjects.legacy_subject,
      subjects.legacy_row_count,
      coalesce(
        array_agg(distinct identities.black_crown_user_id order by identities.black_crown_user_id)
          filter (where identities.black_crown_user_id is not null),
        array[]::uuid[]
      ) as candidate_user_ids
    from subjects
    left join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = subjects.legacy_subject
     and identities.status = 'active'
    group by subjects.legacy_subject, subjects.legacy_row_count
  ), normalized as (
    select
      legacy_subject,
      legacy_row_count,
      candidate_user_ids,
      case cardinality(candidate_user_ids)
        when 0 then 'unresolved'
        when 1 then 'resolved'
        else 'conflict'
      end as state,
      case when cardinality(candidate_user_ids) = 1 then candidate_user_ids[1] else null end as owner_id,
      case cardinality(candidate_user_ids)
        when 0 then 'active_telegram_identity_missing'
        when 1 then 'active_telegram_identity_resolved'
        else 'multiple_active_telegram_identities'
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
    'analytics_activity',
    'telegram',
    public.black_crown_legacy_subject_hash('telegram', legacy_subject),
    state,
    owner_id,
    candidate_user_ids,
    legacy_row_count,
    1,
    reason,
    jsonb_build_object(
      'authority', 'active_telegram_identity',
      'raw_subject_stored', false
    ),
    now(),
    now(),
    case when state = 'resolved' then now() else null end
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

  -- Entitlements remain site-user keyed until the entitlement runtime cutover.
  with subjects as (
    select site_user_id as legacy_subject, count(*)::bigint as legacy_row_count
    from public.blackcrown_entitlements
    group by site_user_id
  ), candidates as (
    select
      subjects.legacy_subject,
      subjects.legacy_row_count,
      coalesce(
        array_agg(distinct identities.black_crown_user_id order by identities.black_crown_user_id)
          filter (where identities.black_crown_user_id is not null),
        array[]::uuid[]
      ) as candidate_user_ids
    from subjects
    left join public.black_crown_identities as identities
      on identities.provider = 'website_auth'
     and identities.provider_subject = subjects.legacy_subject
     and identities.status = 'active'
    group by subjects.legacy_subject, subjects.legacy_row_count
  ), normalized as (
    select
      legacy_subject,
      legacy_row_count,
      candidate_user_ids,
      case cardinality(candidate_user_ids)
        when 0 then 'unresolved'
        when 1 then 'resolved'
        else 'conflict'
      end as state,
      case when cardinality(candidate_user_ids) = 1 then candidate_user_ids[1] else null end as owner_id,
      case cardinality(candidate_user_ids)
        when 0 then 'active_website_identity_missing'
        when 1 then 'active_website_identity_resolved'
        else 'multiple_active_website_identities'
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
    'entitlement',
    'website_auth',
    public.black_crown_legacy_subject_hash('website_auth', legacy_subject),
    state,
    owner_id,
    candidate_user_ids,
    legacy_row_count,
    1,
    reason,
    jsonb_build_object(
      'authority', 'active_website_identity',
      'raw_subject_stored', false
    ),
    now(),
    now(),
    case when state = 'resolved' then now() else null end
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

  -- Legacy account links require agreement between Telegram and Website identity.
  -- A disagreement is merge_pending and never receives an owner automatically.
  with link_rows as (
    select
      links.site_user_id,
      links.telegram_user_id,
      telegram_identity.black_crown_user_id as telegram_owner,
      website_identity.black_crown_user_id as website_owner
    from public.blackcrown_account_links as links
    left join public.black_crown_identities as telegram_identity
      on telegram_identity.provider = 'telegram'
     and telegram_identity.provider_subject = links.telegram_user_id::text
     and telegram_identity.status = 'active'
    left join public.black_crown_identities as website_identity
      on website_identity.provider = 'website_auth'
     and website_identity.provider_subject = links.site_user_id
     and website_identity.status = 'active'
  ), normalized as (
    select
      site_user_id,
      telegram_user_id,
      telegram_owner,
      website_owner,
      case
        when telegram_owner is not null and website_owner = telegram_owner then 'resolved'
        when telegram_owner is not null and website_owner is not null and website_owner <> telegram_owner then 'merge_pending'
        else 'unresolved'
      end as state,
      case
        when telegram_owner is not null and website_owner = telegram_owner then telegram_owner
        else null
      end as owner_id,
      case
        when telegram_owner is null and website_owner is null then array[]::uuid[]
        when telegram_owner is null then array[website_owner]
        when website_owner is null then array[telegram_owner]
        when telegram_owner = website_owner then array[telegram_owner]
        when telegram_owner::text < website_owner::text then array[telegram_owner, website_owner]
        else array[website_owner, telegram_owner]
      end as candidate_user_ids,
      case
        when telegram_owner is not null and website_owner = telegram_owner then 'linked_identities_agree'
        when telegram_owner is not null and website_owner is not null and website_owner <> telegram_owner then 'canonical_identity_conflict'
        when telegram_owner is null and website_owner is null then 'linked_identities_missing'
        when telegram_owner is null then 'telegram_identity_missing'
        else 'website_identity_missing'
      end as reason
    from link_rows
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
      site_user_id || ':' || telegram_user_id::text
    ),
    state,
    owner_id,
    candidate_user_ids,
    1,
    1,
    reason,
    jsonb_build_object(
      'authority', 'telegram_and_website_identity_agreement',
      'raw_subject_stored', false,
      'silent_merge_allowed', false
    ),
    now(),
    now(),
    case when state = 'resolved' then now() else null end
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

  select jsonb_build_object(
    'resolved', count(*) filter (where state = 'resolved'),
    'unresolved', count(*) filter (where state = 'unresolved'),
    'conflict', count(*) filter (where state = 'conflict'),
    'merge_pending', count(*) filter (where state = 'merge_pending')
  )
  into result
  from public.black_crown_ownership_migration_state;

  return coalesce(result, '{}'::jsonb);
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

revoke all on table public.black_crown_ownership_coverage from public, anon, authenticated;
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
  batch_size integer := greatest(1, least(coalesce(p_batch_size, 5000), 50000));
  run_id uuid := extensions.gen_random_uuid();
  affected integer;
  updates jsonb := '{}'::jsonb;
  state_metrics jsonb;
  coverage_metrics jsonb;
begin
  insert into public.black_crown_ownership_migration_runs (
    run_id,
    status,
    batch_size,
    metrics
  ) values (
    run_id,
    'running',
    batch_size,
    '{}'::jsonb
  );

  with candidates as (
    select players.ctid as row_id, identities.black_crown_user_id
    from public.bco_players as players
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = players.chat_id::text
     and identities.status = 'active'
    where players.black_crown_user_id is null
    order by players.chat_id
    limit batch_size
  )
  update public.bco_players as players
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where players.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_players', affected);

  with candidates as (
    select messages.ctid as row_id, identities.black_crown_user_id
    from public.bco_messages as messages
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = messages.chat_id::text
     and identities.status = 'active'
    where messages.black_crown_user_id is null
    order by messages.id
    limit batch_size
  )
  update public.bco_messages as messages
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where messages.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_messages', affected);

  with candidates as (
    select episodes.ctid as row_id, identities.black_crown_user_id
    from public.bco_episodes as episodes
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = episodes.chat_id::text
     and identities.status = 'active'
    where episodes.black_crown_user_id is null
    order by episodes.id
    limit batch_size
  )
  update public.bco_episodes as episodes
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where episodes.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_episodes', affected);

  with candidates as (
    select mistakes.ctid as row_id, identities.black_crown_user_id
    from public.bco_player_mistakes as mistakes
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = mistakes.chat_id::text
     and identities.status = 'active'
    where mistakes.black_crown_user_id is null
    order by mistakes.chat_id, mistakes.mistake_key
    limit batch_size
  )
  update public.bco_player_mistakes as mistakes
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where mistakes.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_player_mistakes', affected);

  with candidates as (
    select receipts.ctid as row_id, identities.black_crown_user_id
    from public.bco_mistake_receipts as receipts
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = receipts.chat_id::text
     and identities.status = 'active'
    where receipts.black_crown_user_id is null
    order by receipts.created_at, receipts.operation_id
    limit batch_size
  )
  update public.bco_mistake_receipts as receipts
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where receipts.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_mistake_receipts', affected);

  with candidates as (
    select events.ctid as row_id, identities.black_crown_user_id
    from public.bco_progression_events as events
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = events.chat_id::text
     and identities.status = 'active'
    where events.black_crown_user_id is null
    order by events.id
    limit batch_size
  )
  update public.bco_progression_events as events
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where events.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_progression_events', affected);

  with candidates as (
    select sessions.ctid as row_id, identities.black_crown_user_id
    from public.bco_training_sessions as sessions
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = sessions.chat_id::text
     and identities.status = 'active'
    where sessions.black_crown_user_id is null
    order by sessions.id
    limit batch_size
  )
  update public.bco_training_sessions as sessions
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where sessions.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_training_sessions', affected);

  with candidates as (
    select activity.ctid as row_id, identities.black_crown_user_id
    from public.bco_user_activity as activity
    join public.black_crown_identities as identities
      on identities.provider = 'telegram'
     and identities.provider_subject = activity.telegram_user_id::text
     and identities.status = 'active'
    where activity.black_crown_user_id is null
    order by activity.telegram_user_id
    limit batch_size
  )
  update public.bco_user_activity as activity
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where activity.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('bco_user_activity', affected);

  -- A legacy link receives an owner only when both verified identities agree.
  with candidates as (
    select links.ctid as row_id, telegram_identity.black_crown_user_id
    from public.blackcrown_account_links as links
    join public.black_crown_identities as telegram_identity
      on telegram_identity.provider = 'telegram'
     and telegram_identity.provider_subject = links.telegram_user_id::text
     and telegram_identity.status = 'active'
    join public.black_crown_identities as website_identity
      on website_identity.provider = 'website_auth'
     and website_identity.provider_subject = links.site_user_id
     and website_identity.status = 'active'
     and website_identity.black_crown_user_id = telegram_identity.black_crown_user_id
    where links.black_crown_user_id is null
    order by links.site_user_id
    limit batch_size
  )
  update public.blackcrown_account_links as links
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where links.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('blackcrown_account_links', affected);

  -- Audit events may resolve from one supplied identity, but if both subjects are
  -- present they must both resolve and agree.
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
      and (website_owner is null or telegram_owner is null or website_owner = telegram_owner)
    order by row_id
    limit batch_size
  )
  update public.blackcrown_account_link_events as events
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where events.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('blackcrown_account_link_events', affected);

  with candidates as (
    select entitlements.ctid as row_id, identities.black_crown_user_id
    from public.blackcrown_entitlements as entitlements
    join public.black_crown_identities as identities
      on identities.provider = 'website_auth'
     and identities.provider_subject = entitlements.site_user_id
     and identities.status = 'active'
    where entitlements.black_crown_user_id is null
    order by entitlements.id
    limit batch_size
  )
  update public.blackcrown_entitlements as entitlements
  set black_crown_user_id = candidates.black_crown_user_id
  from candidates
  where entitlements.ctid = candidates.row_id;
  get diagnostics affected = row_count;
  updates := updates || jsonb_build_object('blackcrown_entitlements', affected);

  select public.black_crown_refresh_ownership_migration_state()
  into state_metrics;

  select coalesce(
    jsonb_object_agg(
      table_name,
      jsonb_build_object(
        'total_rows', total_rows,
        'canonical_rows', canonical_rows,
        'legacy_only_rows', legacy_only_rows,
        'coverage_percent', coverage_percent
      )
    ),
    '{}'::jsonb
  )
  into coverage_metrics
  from public.black_crown_ownership_coverage;

  update public.black_crown_ownership_migration_runs
  set
    status = 'completed',
    metrics = jsonb_build_object(
      'updated_rows', updates,
      'mapping_state', state_metrics,
      'coverage', coverage_metrics
    ),
    completed_at = now()
  where black_crown_ownership_migration_runs.run_id = black_crown_backfill_product_ownership.run_id;

  return jsonb_build_object(
    'ok', true,
    'run_id', run_id,
    'schema_version', 'bco-canonical-owner-v1',
    'batch_size', batch_size,
    'updated_rows', updates,
    'mapping_state', state_metrics,
    'coverage', coverage_metrics
  );
end;
$function$;

revoke all on function public.black_crown_backfill_product_ownership(integer)
  from public, anon, authenticated;
grant execute on function public.black_crown_backfill_product_ownership(integer)
  to service_role;

comment on function public.black_crown_backfill_product_ownership(integer) is
  'Idempotent/resumable canonical owner backfill. Never creates or merges accounts and never overwrites a non-null owner.';
comment on view public.black_crown_ownership_coverage is
  'Privacy-safe canonical ownership coverage counts. Raw identity subjects are not exposed.';

-- Initial bounded pass. Re-running the function is safe and resumes only rows
-- that still have no canonical projection.
select public.black_crown_backfill_product_ownership(50000);
