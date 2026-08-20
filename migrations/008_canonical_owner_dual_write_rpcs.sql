-- BLACK CROWN canonical owner dual-write RPCs (Phase 2B)
--
-- The runtime still writes every legacy key. A canonical owner is accepted only
-- from service-role backend code, re-verified against an active Telegram
-- identity, and never overwrites a different non-null owner.

create or replace function public.black_crown_verified_telegram_owner(
  p_telegram_user_id bigint,
  p_candidate_user_id uuid
)
returns uuid
language sql
stable
security definer
set search_path = public, pg_temp
as $function$
  select identity.black_crown_user_id
  from public.black_crown_identities as identity
  where p_candidate_user_id is not null
    and identity.provider = 'telegram'
    and identity.provider_subject = p_telegram_user_id::text
    and identity.status = 'active'
    and identity.black_crown_user_id = p_candidate_user_id
  limit 1;
$function$;

revoke all on function public.black_crown_verified_telegram_owner(bigint, uuid)
  from public, anon, authenticated;
grant execute on function public.black_crown_verified_telegram_owner(bigint, uuid)
  to service_role;

create or replace function public.black_crown_preserve_owner(
  p_scope text,
  p_telegram_user_id bigint,
  p_existing_user_id uuid,
  p_candidate_user_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $function$
declare
  v_verified uuid;
  v_candidates uuid[];
begin
  v_verified := public.black_crown_verified_telegram_owner(
    p_telegram_user_id,
    p_candidate_user_id
  );

  if p_existing_user_id is null then
    return v_verified;
  end if;
  if v_verified is null or v_verified = p_existing_user_id then
    return p_existing_user_id;
  end if;

  select array_agg(candidate order by candidate)
  into v_candidates
  from (
    select distinct candidate
    from unnest(array[p_existing_user_id, v_verified]::uuid[]) as valueset(candidate)
  ) as unique_candidates;

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
    left(coalesce(nullif(trim(p_scope), ''), 'product_state'), 64),
    'telegram',
    public.black_crown_legacy_subject_hash('telegram', p_telegram_user_id::text),
    'conflict',
    null,
    v_candidates,
    1,
    1,
    'existing_owner_differs_from_active_identity',
    jsonb_build_object(
      'authority', 'server_dual_write',
      'raw_subject_stored', false,
      'owner_overwrite_allowed', false,
      'silent_merge_allowed', false
    ),
    now(),
    now(),
    null
  )
  on conflict (scope, legacy_provider, legacy_subject_hash)
  do update set
    state = 'conflict',
    black_crown_user_id = null,
    candidate_user_ids = excluded.candidate_user_ids,
    legacy_row_count = greatest(state.legacy_row_count, 1),
    attempt_count = state.attempt_count + 1,
    last_reason = excluded.last_reason,
    metadata = excluded.metadata,
    last_attempt_at = now(),
    resolved_at = null;

  return p_existing_user_id;
end;
$function$;

revoke all on function public.black_crown_preserve_owner(text, bigint, uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.black_crown_preserve_owner(text, bigint, uuid, uuid)
  to service_role;

create or replace function public.bco_patch_player_owned(
  p_chat_id bigint,
  p_profile jsonb default null,
  p_summary text default null,
  p_derived jsonb default null,
  p_black_crown_user_id uuid default null
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_existing uuid;
  v_owner uuid;
begin
  select player.black_crown_user_id
  into v_existing
  from public.bco_players as player
  where player.chat_id = p_chat_id
  for update;

  v_owner := public.black_crown_preserve_owner(
    'bco_players', p_chat_id, v_existing, p_black_crown_user_id
  );

  insert into public.bco_players (
    chat_id, profile, summary, derived_intelligence,
    black_crown_user_id, updated_at
  ) values (
    p_chat_id,
    coalesce(p_profile, '{}'::jsonb),
    coalesce(p_summary, ''),
    coalesce(p_derived, '{}'::jsonb),
    v_owner,
    now()
  )
  on conflict (chat_id) do update set
    profile = case
      when p_profile is null then public.bco_players.profile
      else coalesce(public.bco_players.profile, '{}'::jsonb) || p_profile
    end,
    summary = case
      when p_summary is null then public.bco_players.summary
      else p_summary
    end,
    derived_intelligence = case
      when p_derived is null then public.bco_players.derived_intelligence
      else p_derived
    end,
    black_crown_user_id = coalesce(
      public.bco_players.black_crown_user_id,
      excluded.black_crown_user_id
    ),
    updated_at = now();
end;
$function$;

revoke all on function public.bco_patch_player_owned(bigint, jsonb, text, jsonb, uuid)
  from public, anon, authenticated;
grant execute on function public.bco_patch_player_owned(bigint, jsonb, text, jsonb, uuid)
  to service_role;

create or replace function public.bco_record_mistake_owned(
  p_chat_id bigint,
  p_mistake_key text,
  p_label text,
  p_evidence jsonb default '{}'::jsonb,
  p_black_crown_user_id uuid default null
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_existing uuid;
  v_owner uuid;
begin
  select mistake.black_crown_user_id
  into v_existing
  from public.bco_player_mistakes as mistake
  where mistake.chat_id = p_chat_id
    and mistake.mistake_key = p_mistake_key
  for update;

  v_owner := public.black_crown_preserve_owner(
    'bco_player_mistakes', p_chat_id, v_existing, p_black_crown_user_id
  );

  insert into public.bco_player_mistakes (
    chat_id, mistake_key, label, count, evidence, black_crown_user_id
  ) values (
    p_chat_id, p_mistake_key, p_label, 1,
    coalesce(p_evidence, '{}'::jsonb), v_owner
  )
  on conflict (chat_id, mistake_key) do update set
    label = excluded.label,
    count = public.bco_player_mistakes.count + 1,
    last_seen = now(),
    evidence = coalesce(public.bco_player_mistakes.evidence, '{}'::jsonb)
      || coalesce(excluded.evidence, '{}'::jsonb),
    black_crown_user_id = coalesce(
      public.bco_player_mistakes.black_crown_user_id,
      excluded.black_crown_user_id
    );
end;
$function$;

revoke all on function public.bco_record_mistake_owned(bigint, text, text, jsonb, uuid)
  from public, anon, authenticated;
grant execute on function public.bco_record_mistake_owned(bigint, text, text, jsonb, uuid)
  to service_role;

create or replace function public.bco_record_mistake_once_owned(
  p_operation_id text,
  p_chat_id bigint,
  p_mistake_key text,
  p_label text,
  p_evidence jsonb default '{}'::jsonb,
  p_black_crown_user_id uuid default null
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_inserted integer := 0;
  v_receipt_existing uuid;
  v_mistake_existing uuid;
  v_receipt_owner uuid;
  v_mistake_owner uuid;
begin
  if p_operation_id is null or length(trim(p_operation_id)) < 8 then
    raise exception 'operation_id is required';
  end if;

  select receipt.black_crown_user_id
  into v_receipt_existing
  from public.bco_mistake_receipts as receipt
  where receipt.operation_id = p_operation_id
  for update;

  v_receipt_owner := public.black_crown_preserve_owner(
    'bco_mistake_receipts', p_chat_id,
    v_receipt_existing, p_black_crown_user_id
  );

  insert into public.bco_mistake_receipts (
    operation_id, chat_id, mistake_key, black_crown_user_id
  ) values (
    p_operation_id, p_chat_id, p_mistake_key, v_receipt_owner
  )
  on conflict (operation_id) do nothing;

  get diagnostics v_inserted = row_count;
  if v_inserted = 0 then
    return false;
  end if;

  select mistake.black_crown_user_id
  into v_mistake_existing
  from public.bco_player_mistakes as mistake
  where mistake.chat_id = p_chat_id
    and mistake.mistake_key = p_mistake_key
  for update;

  v_mistake_owner := public.black_crown_preserve_owner(
    'bco_player_mistakes', p_chat_id,
    v_mistake_existing, p_black_crown_user_id
  );

  insert into public.bco_player_mistakes (
    chat_id, mistake_key, label, count, evidence, black_crown_user_id
  ) values (
    p_chat_id, p_mistake_key, p_label, 1,
    coalesce(p_evidence, '{}'::jsonb), v_mistake_owner
  )
  on conflict (chat_id, mistake_key) do update set
    label = excluded.label,
    count = public.bco_player_mistakes.count + 1,
    last_seen = now(),
    evidence = coalesce(public.bco_player_mistakes.evidence, '{}'::jsonb)
      || coalesce(excluded.evidence, '{}'::jsonb),
    black_crown_user_id = coalesce(
      public.bco_player_mistakes.black_crown_user_id,
      excluded.black_crown_user_id
    );

  return true;
end;
$function$;

revoke all on function public.bco_record_mistake_once_owned(text, bigint, text, text, jsonb, uuid)
  from public, anon, authenticated;
grant execute on function public.bco_record_mistake_once_owned(text, bigint, text, text, jsonb, uuid)
  to service_role;

create or replace function public.bco_record_user_activity_owned(
  p_user_id bigint,
  p_chat_id bigint,
  p_language text default null,
  p_surface text default 'telegram',
  p_is_message boolean default false,
  p_is_voice boolean default false,
  p_is_miniapp boolean default false,
  p_black_crown_user_id uuid default null
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_existing uuid;
  v_owner uuid;
begin
  select activity.black_crown_user_id
  into v_existing
  from public.bco_user_activity as activity
  where activity.telegram_user_id = p_user_id
  for update;

  v_owner := public.black_crown_preserve_owner(
    'bco_user_activity', p_user_id, v_existing, p_black_crown_user_id
  );

  insert into public.bco_user_activity (
    telegram_user_id, telegram_chat_id, first_seen_at, last_seen_at,
    last_language, last_surface, update_count, message_count,
    voice_count, miniapp_count, black_crown_user_id
  ) values (
    p_user_id, p_chat_id, now(), now(),
    left(coalesce(p_language, ''), 16),
    left(coalesce(p_surface, 'telegram'), 32),
    1,
    case when p_is_message then 1 else 0 end,
    case when p_is_voice then 1 else 0 end,
    case when p_is_miniapp then 1 else 0 end,
    v_owner
  )
  on conflict (telegram_user_id) do update set
    telegram_chat_id = excluded.telegram_chat_id,
    last_seen_at = now(),
    last_language = case
      when excluded.last_language <> '' then excluded.last_language
      else public.bco_user_activity.last_language
    end,
    last_surface = excluded.last_surface,
    update_count = public.bco_user_activity.update_count + 1,
    message_count = public.bco_user_activity.message_count
      + case when p_is_message then 1 else 0 end,
    voice_count = public.bco_user_activity.voice_count
      + case when p_is_voice then 1 else 0 end,
    miniapp_count = public.bco_user_activity.miniapp_count
      + case when p_is_miniapp then 1 else 0 end,
    black_crown_user_id = coalesce(
      public.bco_user_activity.black_crown_user_id,
      excluded.black_crown_user_id
    );
end;
$function$;

revoke all on function public.bco_record_user_activity_owned(bigint, bigint, text, text, boolean, boolean, boolean, uuid)
  from public, anon, authenticated;
grant execute on function public.bco_record_user_activity_owned(bigint, bigint, text, text, boolean, boolean, boolean, uuid)
  to service_role;
