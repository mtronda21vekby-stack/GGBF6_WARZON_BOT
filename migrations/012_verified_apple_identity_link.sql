-- V2 Phase 4B.3: verified Apple identity linking through an existing Telegram identity.
-- The iOS client never selects a canonical account. A private Telegram message is
-- the ownership proof, and the service-role-only completion function performs the
-- identity write atomically.

create table if not exists public.black_crown_apple_link_challenges (
  id uuid primary key default extensions.gen_random_uuid(),
  apple_provider_subject text not null,
  apple_provider_subject_hash text not null,
  code_hash text not null unique,
  purpose text not null default 'link_apple_to_existing_account',
  status text not null default 'pending',
  black_crown_user_id uuid references public.black_crown_accounts(black_crown_user_id) on delete restrict,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  completed_at timestamptz,
  cancelled_at timestamptz,
  updated_at timestamptz not null default now(),
  constraint black_crown_apple_link_subject_uuid_check
    check (apple_provider_subject ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'),
  constraint black_crown_apple_link_subject_hash_check
    check (apple_provider_subject_hash ~ '^[0-9a-f]{64}$'),
  constraint black_crown_apple_link_code_hash_check
    check (code_hash ~ '^[0-9a-f]{64}$'),
  constraint black_crown_apple_link_purpose_check
    check (purpose = 'link_apple_to_existing_account'),
  constraint black_crown_apple_link_status_check
    check (status in ('pending','linked','expired','cancelled','conflict')),
  constraint black_crown_apple_link_expiry_check
    check (expires_at > created_at),
  constraint black_crown_apple_link_terminal_check
    check (
      (status = 'linked' and black_crown_user_id is not null and completed_at is not null)
      or (status = 'cancelled' and cancelled_at is not null)
      or status in ('pending','expired','conflict')
    )
);

create index if not exists black_crown_apple_link_subject_status_idx
  on public.black_crown_apple_link_challenges (apple_provider_subject, status, expires_at desc);

alter table public.black_crown_apple_link_challenges enable row level security;
revoke all on table public.black_crown_apple_link_challenges from public, anon, authenticated;
grant select, insert, update on table public.black_crown_apple_link_challenges to service_role;

create or replace function public.black_crown_start_apple_telegram_link(
  p_apple_subject text,
  p_code_hash text,
  p_ttl_seconds integer default 600
)
returns jsonb
language plpgsql
security definer
set search_path to 'public','extensions'
as $function$
declare
  v_link_id uuid;
  v_expires_at timestamptz;
  v_existing public.black_crown_identities%rowtype;
  v_ttl integer;
begin
  if p_apple_subject is null
     or p_apple_subject !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then
    return jsonb_build_object('ok', false, 'reason', 'invalid_apple_identity');
  end if;
  if p_code_hash is null or p_code_hash !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'reason', 'invalid_challenge_hash');
  end if;

  select * into v_existing
    from public.black_crown_identities
   where provider = 'apple' and provider_subject = p_apple_subject
   for update;
  if found then
    if v_existing.status = 'active' then
      return jsonb_build_object('ok', true, 'status', 'linked');
    end if;
    return jsonb_build_object('ok', false, 'reason', 'apple_identity_conflict');
  end if;

  update public.black_crown_apple_link_challenges
     set status = 'cancelled', cancelled_at = now(), updated_at = now()
   where apple_provider_subject = p_apple_subject
     and status = 'pending';

  v_ttl := greatest(60, least(coalesce(p_ttl_seconds, 600), 900));
  v_expires_at := now() + make_interval(secs => v_ttl);
  insert into public.black_crown_apple_link_challenges (
    apple_provider_subject,
    apple_provider_subject_hash,
    code_hash,
    expires_at
  ) values (
    p_apple_subject,
    encode(extensions.digest(convert_to(p_apple_subject, 'UTF8'), 'sha256'), 'hex'),
    p_code_hash,
    v_expires_at
  ) returning id into v_link_id;

  return jsonb_build_object(
    'ok', true,
    'status', 'pending',
    'link_id', v_link_id,
    'expires_at', v_expires_at,
    'ttl_seconds', v_ttl
  );
exception when unique_violation then
  return jsonb_build_object('ok', false, 'reason', 'challenge_conflict');
end;
$function$;

create or replace function public.black_crown_get_apple_telegram_link_status(
  p_link_id uuid,
  p_apple_subject text
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_challenge public.black_crown_apple_link_challenges%rowtype;
begin
  if p_link_id is null or p_apple_subject is null then
    return jsonb_build_object('ok', false, 'reason', 'link_not_found');
  end if;
  select * into v_challenge
    from public.black_crown_apple_link_challenges
   where id = p_link_id and apple_provider_subject = p_apple_subject
   for update;
  if not found then
    return jsonb_build_object('ok', false, 'reason', 'link_not_found');
  end if;
  if v_challenge.status = 'pending' and v_challenge.expires_at <= now() then
    update public.black_crown_apple_link_challenges
       set status = 'expired', updated_at = now()
     where id = v_challenge.id;
    v_challenge.status := 'expired';
  end if;
  return jsonb_build_object(
    'ok', true,
    'status', v_challenge.status,
    'expires_at', v_challenge.expires_at
  );
end;
$function$;

create or replace function public.black_crown_cancel_apple_telegram_link(
  p_link_id uuid,
  p_apple_subject text
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_status text;
begin
  select status into v_status
    from public.black_crown_apple_link_challenges
   where id = p_link_id and apple_provider_subject = p_apple_subject
   for update;
  if not found then
    return jsonb_build_object('ok', false, 'reason', 'link_not_found');
  end if;
  if v_status = 'pending' then
    update public.black_crown_apple_link_challenges
       set status = 'cancelled', cancelled_at = now(), updated_at = now()
     where id = p_link_id;
    v_status := 'cancelled';
  end if;
  return jsonb_build_object('ok', true, 'status', v_status);
end;
$function$;

create or replace function public.black_crown_complete_apple_telegram_link(
  p_code text,
  p_telegram_user_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path to 'public','extensions'
as $function$
declare
  v_hash text;
  v_challenge public.black_crown_apple_link_challenges%rowtype;
  v_target uuid;
  v_existing public.black_crown_identities%rowtype;
begin
  if p_code is null or length(p_code) < 32 or length(p_code) > 128
     or p_code !~ '^[A-Za-z0-9_-]+$' then
    return jsonb_build_object('ok', false, 'reason', 'invalid_or_expired_code');
  end if;
  if p_telegram_user_id is null or p_telegram_user_id <= 0 then
    return jsonb_build_object('ok', false, 'reason', 'invalid_telegram_identity');
  end if;

  v_hash := encode(extensions.digest(convert_to(p_code, 'UTF8'), 'sha256'), 'hex');
  select * into v_challenge
    from public.black_crown_apple_link_challenges
   where code_hash = v_hash
   for update;
  if not found then
    return jsonb_build_object('ok', false, 'reason', 'invalid_or_expired_code');
  end if;
  if v_challenge.status = 'linked' then
    return jsonb_build_object('ok', true, 'status', 'linked', 'replayed', true);
  end if;
  if v_challenge.status <> 'pending' then
    return jsonb_build_object('ok', false, 'reason', 'link_' || v_challenge.status);
  end if;
  if v_challenge.expires_at <= now() then
    update public.black_crown_apple_link_challenges
       set status = 'expired', updated_at = now()
     where id = v_challenge.id;
    return jsonb_build_object('ok', false, 'reason', 'link_expired');
  end if;

  select identities.black_crown_user_id into v_target
    from public.black_crown_identities as identities
    join public.black_crown_accounts as accounts
      on accounts.black_crown_user_id = identities.black_crown_user_id
   where identities.provider = 'telegram'
     and identities.provider_subject = p_telegram_user_id::text
     and identities.status = 'active'
     and accounts.account_status = 'active'
   for update of identities, accounts;
  if v_target is null then
    return jsonb_build_object('ok', false, 'reason', 'verified_account_not_found');
  end if;
  if not exists (
    select 1 from public.black_crown_identities
     where black_crown_user_id = v_target
       and provider = 'website_auth'
       and status = 'active'
  ) then
    return jsonb_build_object('ok', false, 'reason', 'existing_account_proof_incomplete');
  end if;

  select * into v_existing
    from public.black_crown_identities
   where provider = 'apple'
     and provider_subject = v_challenge.apple_provider_subject
   for update;
  if found and (
    v_existing.black_crown_user_id <> v_target or v_existing.status <> 'active'
  ) then
    update public.black_crown_apple_link_challenges
       set status = 'conflict', updated_at = now()
     where id = v_challenge.id;
    insert into public.black_crown_identity_events (
      black_crown_user_id, event_type, provider, provider_subject_hash, metadata
    ) values (
      v_target,
      'apple_identity_link_conflict',
      'apple',
      v_challenge.apple_provider_subject_hash,
      jsonb_build_object('source', 'telegram_one_time_challenge', 'link_id', v_challenge.id)
    );
    return jsonb_build_object('ok', false, 'reason', 'apple_identity_conflict');
  end if;

  if not found then
    insert into public.black_crown_identities (
      black_crown_user_id, provider, provider_subject, status, metadata, verified_at
    ) values (
      v_target,
      'apple',
      v_challenge.apple_provider_subject,
      'active',
      jsonb_build_object('linked_via', 'telegram_one_time_challenge', 'link_id', v_challenge.id),
      now()
    );
  end if;

  update public.black_crown_apple_link_challenges
     set status = 'linked',
         black_crown_user_id = v_target,
         completed_at = coalesce(completed_at, now()),
         updated_at = now()
   where id = v_challenge.id;
  insert into public.black_crown_identity_events (
    black_crown_user_id, event_type, provider, provider_subject_hash, metadata
  ) values (
    v_target,
    'apple_identity_linked',
    'apple',
    v_challenge.apple_provider_subject_hash,
    jsonb_build_object('source', 'telegram_one_time_challenge', 'link_id', v_challenge.id)
  );
  return jsonb_build_object('ok', true, 'status', 'linked', 'replayed', false);
exception when unique_violation then
  update public.black_crown_apple_link_challenges
     set status = 'conflict', updated_at = now()
   where id = v_challenge.id;
  return jsonb_build_object('ok', false, 'reason', 'apple_identity_conflict');
end;
$function$;

revoke all on function public.black_crown_start_apple_telegram_link(text, text, integer)
  from public, anon, authenticated;
revoke all on function public.black_crown_get_apple_telegram_link_status(uuid, text)
  from public, anon, authenticated;
revoke all on function public.black_crown_cancel_apple_telegram_link(uuid, text)
  from public, anon, authenticated;
revoke all on function public.black_crown_complete_apple_telegram_link(text, bigint)
  from public, anon, authenticated;
grant execute on function public.black_crown_start_apple_telegram_link(text, text, integer) to service_role;
grant execute on function public.black_crown_get_apple_telegram_link_status(uuid, text) to service_role;
grant execute on function public.black_crown_cancel_apple_telegram_link(uuid, text) to service_role;
grant execute on function public.black_crown_complete_apple_telegram_link(text, bigint) to service_role;

comment on table public.black_crown_apple_link_challenges is
  'Service-role-only, short-lived, replay-protected Apple to existing BLACK CROWN account link challenges.';
