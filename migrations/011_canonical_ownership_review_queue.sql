-- BLACK CROWN canonical ownership review queue (Phase 2D foundation)
--
-- This migration creates a service-role-only review and pending-confirmation
-- contract for unresolved/conflicting legacy ownership. It deliberately cannot:
--   * create an account or identity;
--   * assign black_crown_user_id to product rows;
--   * merge canonical accounts;
--   * transfer Premium/entitlements;
--   * mark a case resolved;
--   * store a raw Telegram/Website provider subject.
--
-- Existing legacy and canonical product data remain unchanged.

create table if not exists public.black_crown_ownership_resolution_cases (
  case_id uuid primary key default extensions.gen_random_uuid(),
  legacy_provider text not null,
  legacy_subject_hash text not null,
  case_state text not null default 'open',
  affected_scopes text[] not null default array[]::text[],
  source_states text[] not null default array[]::text[],
  candidate_user_ids uuid[] not null default array[]::uuid[],
  legacy_row_count bigint not null default 0,
  risk_flags text[] not null default array[]::text[],
  proposed_black_crown_user_id uuid null,
  confirmation_method text null,
  confirmation_state text not null default 'not_started',
  revision integer not null default 1,
  automatic_resolution_allowed boolean not null default false,
  owner_write_allowed boolean not null default false,
  entitlement_transfer_allowed boolean not null default false,
  first_seen_at timestamptz not null default now(),
  last_refreshed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (legacy_provider, legacy_subject_hash),
  constraint black_crown_ownership_resolution_hash_check
    check (legacy_subject_hash ~ '^[0-9a-f]{64}$'),
  constraint black_crown_ownership_resolution_case_state_check
    check (case_state in ('open', 'blocked', 'awaiting_confirmation', 'superseded')),
  constraint black_crown_ownership_resolution_confirmation_state_check
    check (confirmation_state in ('not_started', 'pending')),
  constraint black_crown_ownership_resolution_confirmation_method_check
    check (
      confirmation_method is null
      or confirmation_method in (
        'telegram_challenge',
        'website_session',
        'support_dual_confirmation'
      )
    ),
  constraint black_crown_ownership_resolution_confirmation_shape_check
    check (
      (
        case_state = 'awaiting_confirmation'
        and proposed_black_crown_user_id is not null
        and confirmation_method is not null
        and confirmation_state = 'pending'
      )
      or
      (
        case_state <> 'awaiting_confirmation'
        and proposed_black_crown_user_id is null
        and confirmation_method is null
        and confirmation_state = 'not_started'
      )
    ),
  constraint black_crown_ownership_resolution_rows_check
    check (legacy_row_count >= 0),
  constraint black_crown_ownership_resolution_revision_check
    check (revision >= 1),
  constraint black_crown_ownership_resolution_no_automatic_resolution_check
    check (automatic_resolution_allowed = false),
  constraint black_crown_ownership_resolution_no_owner_write_check
    check (owner_write_allowed = false),
  constraint black_crown_ownership_resolution_no_entitlement_transfer_check
    check (entitlement_transfer_allowed = false),
  constraint black_crown_ownership_resolution_proposed_account_fkey
    foreign key (proposed_black_crown_user_id)
    references public.black_crown_accounts (black_crown_user_id)
    on delete restrict
);

create index if not exists black_crown_ownership_resolution_state_idx
  on public.black_crown_ownership_resolution_cases (
    case_state,
    last_refreshed_at desc
  );
create index if not exists black_crown_ownership_resolution_proposed_user_idx
  on public.black_crown_ownership_resolution_cases (
    proposed_black_crown_user_id
  )
  where proposed_black_crown_user_id is not null;

alter table public.black_crown_ownership_resolution_cases
  enable row level security;
revoke all on table public.black_crown_ownership_resolution_cases
  from public, anon, authenticated;
grant select, insert, update, delete
  on table public.black_crown_ownership_resolution_cases
  to service_role;

do $policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'black_crown_ownership_resolution_cases'
      and policyname = 'black_crown_ownership_resolution_cases_browser_deny'
  ) then
    create policy black_crown_ownership_resolution_cases_browser_deny
      on public.black_crown_ownership_resolution_cases
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;
end
$policy$;

create table if not exists public.black_crown_ownership_resolution_events (
  event_id uuid primary key default extensions.gen_random_uuid(),
  case_id uuid not null,
  event_type text not null,
  actor_ref_hash text not null,
  reason_code text not null,
  proposed_black_crown_user_id uuid null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint black_crown_ownership_resolution_events_case_fkey
    foreign key (case_id)
    references public.black_crown_ownership_resolution_cases (case_id)
    on delete restrict,
  constraint black_crown_ownership_resolution_events_proposed_account_fkey
    foreign key (proposed_black_crown_user_id)
    references public.black_crown_accounts (black_crown_user_id)
    on delete restrict,
  constraint black_crown_ownership_resolution_events_type_check
    check (event_type in ('confirmation_proposed', 'confirmation_cancelled')),
  constraint black_crown_ownership_resolution_events_actor_hash_check
    check (actor_ref_hash ~ '^[0-9a-f]{64}$'),
  constraint black_crown_ownership_resolution_events_reason_check
    check (reason_code ~ '^[a-z0-9_]{3,64}$'),
  constraint black_crown_ownership_resolution_events_metadata_check
    check (jsonb_typeof(metadata) = 'object')
);

create index if not exists black_crown_ownership_resolution_events_case_idx
  on public.black_crown_ownership_resolution_events (
    case_id,
    created_at desc
  );

alter table public.black_crown_ownership_resolution_events
  enable row level security;
revoke all on table public.black_crown_ownership_resolution_events
  from public, anon, authenticated;
grant select, insert
  on table public.black_crown_ownership_resolution_events
  to service_role;

do $policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'black_crown_ownership_resolution_events'
      and policyname = 'black_crown_ownership_resolution_events_browser_deny'
  ) then
    create policy black_crown_ownership_resolution_events_browser_deny
      on public.black_crown_ownership_resolution_events
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;
end
$policy$;

create or replace function public.black_crown_refresh_ownership_resolution_cases()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_now timestamptz := now();
  v_metrics jsonb;
begin
  perform pg_advisory_xact_lock(
    hashtext('black_crown_ownership_resolution_v1')
  );

  with source as (
    select
      state.legacy_provider,
      state.legacy_subject_hash,
      array_agg(distinct state.scope order by state.scope) as affected_scopes,
      array_agg(distinct state.state order by state.state) as source_states,
      sum(state.legacy_row_count)::bigint as legacy_row_count,
      bool_or(state.state = 'unresolved') as has_unresolved,
      bool_or(state.state = 'conflict') as has_conflict,
      bool_or(state.state = 'merge_pending') as has_merge_pending
    from public.black_crown_ownership_migration_state as state
    where state.state <> 'resolved'
    group by state.legacy_provider, state.legacy_subject_hash
  ), candidates as (
    select
      state.legacy_provider,
      state.legacy_subject_hash,
      coalesce(
        array_agg(distinct candidate.user_id order by candidate.user_id)
          filter (where candidate.user_id is not null),
        array[]::uuid[]
      ) as candidate_user_ids
    from public.black_crown_ownership_migration_state as state
    left join lateral unnest(state.candidate_user_ids)
      as candidate(user_id)
      on true
    where state.state <> 'resolved'
    group by state.legacy_provider, state.legacy_subject_hash
  ), current_cases as (
    select
      source.legacy_provider,
      source.legacy_subject_hash,
      source.affected_scopes,
      source.source_states,
      coalesce(candidates.candidate_user_ids, array[]::uuid[])
        as candidate_user_ids,
      source.legacy_row_count,
      array_remove(
        array[
          case when source.has_unresolved then 'identity_unresolved' end,
          case when source.has_conflict then 'identity_conflict' end,
          case when source.has_merge_pending then 'merge_pending' end
        ]::text[],
        null
      ) as risk_flags,
      case
        when source.has_conflict or source.has_merge_pending then 'blocked'
        else 'open'
      end as suggested_state
    from source
    left join candidates
      on candidates.legacy_provider = source.legacy_provider
     and candidates.legacy_subject_hash = source.legacy_subject_hash
  )
  insert into public.black_crown_ownership_resolution_cases as target (
    legacy_provider,
    legacy_subject_hash,
    case_state,
    affected_scopes,
    source_states,
    candidate_user_ids,
    legacy_row_count,
    risk_flags,
    proposed_black_crown_user_id,
    confirmation_method,
    confirmation_state,
    revision,
    automatic_resolution_allowed,
    owner_write_allowed,
    entitlement_transfer_allowed,
    first_seen_at,
    last_refreshed_at,
    updated_at
  )
  select
    current_cases.legacy_provider,
    current_cases.legacy_subject_hash,
    current_cases.suggested_state,
    current_cases.affected_scopes,
    current_cases.source_states,
    current_cases.candidate_user_ids,
    current_cases.legacy_row_count,
    current_cases.risk_flags,
    null,
    null,
    'not_started',
    1,
    false,
    false,
    false,
    v_now,
    v_now,
    v_now
  from current_cases
  on conflict (legacy_provider, legacy_subject_hash)
  do update set
    affected_scopes = excluded.affected_scopes,
    source_states = excluded.source_states,
    candidate_user_ids = excluded.candidate_user_ids,
    legacy_row_count = excluded.legacy_row_count,
    case_state = case
      when target.case_state = 'awaiting_confirmation'
       and target.affected_scopes = excluded.affected_scopes
       and target.source_states = excluded.source_states
       and target.candidate_user_ids = excluded.candidate_user_ids
       and target.legacy_row_count = excluded.legacy_row_count
        then target.case_state
      else excluded.case_state
    end,
    risk_flags = case
      when target.case_state = 'awaiting_confirmation'
       and target.affected_scopes = excluded.affected_scopes
       and target.source_states = excluded.source_states
       and target.candidate_user_ids = excluded.candidate_user_ids
       and target.legacy_row_count = excluded.legacy_row_count
        then target.risk_flags
      else excluded.risk_flags
    end,
    proposed_black_crown_user_id = case
      when target.case_state = 'awaiting_confirmation'
       and target.affected_scopes = excluded.affected_scopes
       and target.source_states = excluded.source_states
       and target.candidate_user_ids = excluded.candidate_user_ids
       and target.legacy_row_count = excluded.legacy_row_count
        then target.proposed_black_crown_user_id
      else null
    end,
    confirmation_method = case
      when target.case_state = 'awaiting_confirmation'
       and target.affected_scopes = excluded.affected_scopes
       and target.source_states = excluded.source_states
       and target.candidate_user_ids = excluded.candidate_user_ids
       and target.legacy_row_count = excluded.legacy_row_count
        then target.confirmation_method
      else null
    end,
    confirmation_state = case
      when target.case_state = 'awaiting_confirmation'
       and target.affected_scopes = excluded.affected_scopes
       and target.source_states = excluded.source_states
       and target.candidate_user_ids = excluded.candidate_user_ids
       and target.legacy_row_count = excluded.legacy_row_count
        then target.confirmation_state
      else 'not_started'
    end,
    revision = target.revision + case
      when target.affected_scopes is distinct from excluded.affected_scopes
        or target.source_states is distinct from excluded.source_states
        or target.candidate_user_ids is distinct from excluded.candidate_user_ids
        or target.legacy_row_count is distinct from excluded.legacy_row_count
        or (
          target.case_state <> 'awaiting_confirmation'
          and target.case_state is distinct from excluded.case_state
        )
        then 1
      else 0
    end,
    last_refreshed_at = v_now,
    updated_at = case
      when target.affected_scopes is distinct from excluded.affected_scopes
        or target.source_states is distinct from excluded.source_states
        or target.candidate_user_ids is distinct from excluded.candidate_user_ids
        or target.legacy_row_count is distinct from excluded.legacy_row_count
        or (
          target.case_state <> 'awaiting_confirmation'
          and target.case_state is distinct from excluded.case_state
        )
        then v_now
      else target.updated_at
    end;

  update public.black_crown_ownership_resolution_cases as cases
  set
    case_state = 'superseded',
    proposed_black_crown_user_id = null,
    confirmation_method = null,
    confirmation_state = 'not_started',
    risk_flags = array['source_no_longer_unresolved']::text[],
    revision = cases.revision + 1,
    last_refreshed_at = v_now,
    updated_at = v_now
  where cases.case_state <> 'superseded'
    and cases.last_refreshed_at < v_now;

  select jsonb_build_object(
    'schema_version', 'bco-ownership-resolution-v1',
    'total_cases', count(*),
    'open_cases', count(*) filter (where case_state = 'open'),
    'blocked_cases', count(*) filter (where case_state = 'blocked'),
    'awaiting_confirmation_cases', count(*) filter (
      where case_state = 'awaiting_confirmation'
    ),
    'superseded_cases', count(*) filter (where case_state = 'superseded'),
    'automatic_resolution_allowed', false,
    'owner_writes_performed', 0,
    'identity_writes_performed', 0,
    'entitlement_transfers_performed', 0
  )
  into v_metrics
  from public.black_crown_ownership_resolution_cases;

  return coalesce(v_metrics, '{}'::jsonb);
end;
$function$;

revoke all on function public.black_crown_refresh_ownership_resolution_cases()
  from public, anon, authenticated;
grant execute on function public.black_crown_refresh_ownership_resolution_cases()
  to service_role;

create or replace function public.black_crown_begin_ownership_confirmation(
  p_case_id uuid,
  p_expected_revision integer,
  p_proposed_black_crown_user_id uuid,
  p_confirmation_method text,
  p_actor_ref_hash text,
  p_reason_code text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_case public.black_crown_ownership_resolution_cases%rowtype;
  v_method text := trim(coalesce(p_confirmation_method, ''));
  v_actor_ref_hash text := lower(trim(coalesce(p_actor_ref_hash, '')));
  v_reason_code text := lower(trim(coalesce(p_reason_code, '')));
  v_new_revision integer;
begin
  if v_method not in (
    'telegram_challenge',
    'website_session',
    'support_dual_confirmation'
  ) then
    raise exception using
      errcode = '22023',
      message = 'unsupported ownership confirmation method';
  end if;

  if v_actor_ref_hash !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'actor reference hash is required';
  end if;

  if v_reason_code !~ '^[a-z0-9_]{3,64}$' then
    raise exception using
      errcode = '22023',
      message = 'ownership confirmation reason code is invalid';
  end if;

  if p_expected_revision is null or p_expected_revision < 1 then
    raise exception using
      errcode = '22023',
      message = 'expected ownership case revision is required';
  end if;

  if not exists (
    select 1
    from public.black_crown_accounts as account
    where account.black_crown_user_id = p_proposed_black_crown_user_id
      and account.account_status in ('active', 'provisional')
  ) then
    raise exception using
      errcode = '23503',
      message = 'proposed canonical account is not eligible';
  end if;

  select *
  into v_case
  from public.black_crown_ownership_resolution_cases as cases
  where cases.case_id = p_case_id
  for update;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'ownership resolution case not found';
  end if;

  if v_case.revision <> p_expected_revision then
    raise exception using
      errcode = '40001',
      message = 'ownership resolution case revision changed';
  end if;

  if v_case.case_state not in ('open', 'blocked') then
    raise exception using
      errcode = '55000',
      message = 'ownership resolution case is not reviewable';
  end if;

  if v_case.case_state = 'blocked' and (
    v_method <> 'support_dual_confirmation'
    or not (p_proposed_black_crown_user_id = any(v_case.candidate_user_ids))
  ) then
    raise exception using
      errcode = '55000',
      message = 'blocked ownership case requires a candidate and dual confirmation';
  end if;

  update public.black_crown_ownership_resolution_cases as cases
  set
    case_state = 'awaiting_confirmation',
    proposed_black_crown_user_id = p_proposed_black_crown_user_id,
    confirmation_method = v_method,
    confirmation_state = 'pending',
    risk_flags = array(
      select distinct risk_flag
      from unnest(
        cases.risk_flags || array['manual_confirmation_required']::text[]
      ) as flags(risk_flag)
      order by risk_flag
    ),
    revision = cases.revision + 1,
    updated_at = now()
  where cases.case_id = p_case_id
  returning cases.revision into v_new_revision;

  insert into public.black_crown_ownership_resolution_events (
    case_id,
    event_type,
    actor_ref_hash,
    reason_code,
    proposed_black_crown_user_id,
    metadata
  ) values (
    p_case_id,
    'confirmation_proposed',
    v_actor_ref_hash,
    v_reason_code,
    p_proposed_black_crown_user_id,
    jsonb_build_object(
      'confirmation_method', v_method,
      'previous_revision', p_expected_revision,
      'new_revision', v_new_revision,
      'automatic_resolution_allowed', false,
      'owner_write_performed', false,
      'identity_write_performed', false,
      'entitlement_transfer_performed', false,
      'raw_subject_stored', false
    )
  );

  return jsonb_build_object(
    'case_id', p_case_id,
    'case_state', 'awaiting_confirmation',
    'confirmation_state', 'pending',
    'confirmation_method', v_method,
    'revision', v_new_revision,
    'automatic_resolution_allowed', false,
    'owner_write_performed', false,
    'identity_write_performed', false,
    'entitlement_transfer_performed', false
  );
end;
$function$;

revoke all on function public.black_crown_begin_ownership_confirmation(
  uuid, integer, uuid, text, text, text
) from public, anon, authenticated;
grant execute on function public.black_crown_begin_ownership_confirmation(
  uuid, integer, uuid, text, text, text
) to service_role;

create or replace function public.black_crown_cancel_ownership_confirmation(
  p_case_id uuid,
  p_expected_revision integer,
  p_actor_ref_hash text,
  p_reason_code text
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_case public.black_crown_ownership_resolution_cases%rowtype;
  v_actor_ref_hash text := lower(trim(coalesce(p_actor_ref_hash, '')));
  v_reason_code text := lower(trim(coalesce(p_reason_code, '')));
  v_restored_state text;
  v_new_revision integer;
begin
  if v_actor_ref_hash !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'actor reference hash is required';
  end if;

  if v_reason_code !~ '^[a-z0-9_]{3,64}$' then
    raise exception using
      errcode = '22023',
      message = 'ownership confirmation reason code is invalid';
  end if;

  select *
  into v_case
  from public.black_crown_ownership_resolution_cases as cases
  where cases.case_id = p_case_id
  for update;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'ownership resolution case not found';
  end if;

  if v_case.revision <> p_expected_revision then
    raise exception using
      errcode = '40001',
      message = 'ownership resolution case revision changed';
  end if;

  if v_case.case_state <> 'awaiting_confirmation' then
    raise exception using
      errcode = '55000',
      message = 'ownership confirmation is not pending';
  end if;

  v_restored_state := case
    when v_case.source_states && array['conflict', 'merge_pending']::text[]
      then 'blocked'
    else 'open'
  end;

  update public.black_crown_ownership_resolution_cases as cases
  set
    case_state = v_restored_state,
    proposed_black_crown_user_id = null,
    confirmation_method = null,
    confirmation_state = 'not_started',
    risk_flags = array_remove(
      cases.risk_flags,
      'manual_confirmation_required'
    ),
    revision = cases.revision + 1,
    updated_at = now()
  where cases.case_id = p_case_id
  returning cases.revision into v_new_revision;

  insert into public.black_crown_ownership_resolution_events (
    case_id,
    event_type,
    actor_ref_hash,
    reason_code,
    proposed_black_crown_user_id,
    metadata
  ) values (
    p_case_id,
    'confirmation_cancelled',
    v_actor_ref_hash,
    v_reason_code,
    v_case.proposed_black_crown_user_id,
    jsonb_build_object(
      'previous_revision', p_expected_revision,
      'new_revision', v_new_revision,
      'restored_state', v_restored_state,
      'automatic_resolution_allowed', false,
      'owner_write_performed', false,
      'identity_write_performed', false,
      'entitlement_transfer_performed', false,
      'raw_subject_stored', false
    )
  );

  return jsonb_build_object(
    'case_id', p_case_id,
    'case_state', v_restored_state,
    'confirmation_state', 'not_started',
    'revision', v_new_revision,
    'automatic_resolution_allowed', false,
    'owner_write_performed', false,
    'identity_write_performed', false,
    'entitlement_transfer_performed', false
  );
end;
$function$;

revoke all on function public.black_crown_cancel_ownership_confirmation(
  uuid, integer, text, text
) from public, anon, authenticated;
grant execute on function public.black_crown_cancel_ownership_confirmation(
  uuid, integer, text, text
) to service_role;

create or replace view public.black_crown_ownership_resolution_queue
with (security_invoker = true)
as
select
  cases.case_id,
  'bco-ownership-resolution-v1'::text as schema_version,
  cases.legacy_provider,
  cases.legacy_subject_hash,
  cases.case_state,
  cases.affected_scopes,
  cases.source_states,
  cases.legacy_row_count,
  cardinality(cases.candidate_user_ids)::integer as candidate_count,
  cases.risk_flags,
  (cases.proposed_black_crown_user_id is not null) as proposed_owner_present,
  cases.confirmation_method,
  cases.confirmation_state,
  cases.revision,
  cases.automatic_resolution_allowed,
  cases.owner_write_allowed,
  cases.entitlement_transfer_allowed,
  cases.first_seen_at,
  cases.last_refreshed_at,
  cases.updated_at
from public.black_crown_ownership_resolution_cases as cases;

revoke all on table public.black_crown_ownership_resolution_queue
  from public, anon, authenticated;
grant select on table public.black_crown_ownership_resolution_queue
  to service_role;

comment on table public.black_crown_ownership_resolution_cases is
  'Service-role hashed-subject ownership review cases. No raw provider subject and no automatic resolution authority.';
comment on table public.black_crown_ownership_resolution_events is
  'Service-role audit events for pending/cancelled confirmation proposals. Events never apply ownership.';
comment on view public.black_crown_ownership_resolution_queue is
  'Privacy-safe ownership review queue. Candidate IDs and proposed owner IDs are not projected.';
comment on function public.black_crown_begin_ownership_confirmation(
  uuid, integer, uuid, text, text, text
) is
  'Creates a pending confirmation proposal only. Does not write product owners, identities, accounts or entitlements.';

select public.black_crown_refresh_ownership_resolution_cases();
