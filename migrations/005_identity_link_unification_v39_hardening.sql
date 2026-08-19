-- BLACK CROWN v39 hardening: ONE BLACK CROWN ACCOUNT
-- Applied to shared Supabase GAME. Website and Telegram identities are attached
-- to the same canonical black_crown_user_id. Legacy link/profile tables remain
-- intact during the migration window.

create or replace function public.blackcrown_complete_telegram_link(p_code text, p_site_user_id text)
returns jsonb
language plpgsql
security definer
set search_path to 'public','extensions'
as $function$
declare
  v_hash text;
  v_challenge public.blackcrown_telegram_link_challenges%rowtype;
  v_existing_site public.blackcrown_account_links%rowtype;
  v_existing_telegram public.blackcrown_account_links%rowtype;
  v_entitlements text[] := array[]::text[];
  v_premium boolean := false;
  v_event text := 'linked';
  v_crown_user uuid;
  v_existing_web_user uuid;
begin
  if p_code is null or length(p_code) < 32 or length(p_code) > 128 or p_code !~ '^[A-Za-z0-9_-]+$' then
    return jsonb_build_object('ok', false, 'reason', 'invalid_or_expired_code');
  end if;
  if p_site_user_id is null or length(p_site_user_id) < 1 or length(p_site_user_id) > 160 or p_site_user_id !~ '^[A-Za-z0-9_.:@-]+$' then
    return jsonb_build_object('ok', false, 'reason', 'invalid_site_user');
  end if;

  v_hash := encode(extensions.digest(convert_to(p_code, 'UTF8'), 'sha256'), 'hex');
  select * into v_challenge from public.blackcrown_telegram_link_challenges
   where code_hash=v_hash and consumed_at is null and expires_at>now() for update;
  if not found then return jsonb_build_object('ok',false,'reason','invalid_or_expired_code'); end if;

  select * into v_existing_site from public.blackcrown_account_links where site_user_id=p_site_user_id and status='active';
  if found and v_existing_site.telegram_user_id<>v_challenge.telegram_user_id then
    return jsonb_build_object('ok',false,'reason','site_already_linked');
  end if;
  select * into v_existing_telegram from public.blackcrown_account_links where telegram_user_id=v_challenge.telegram_user_id and status='active';
  if found and v_existing_telegram.site_user_id<>p_site_user_id then
    return jsonb_build_object('ok',false,'reason','telegram_already_linked');
  end if;

  select black_crown_user_id into v_crown_user from public.black_crown_identities
   where provider='telegram' and provider_subject=v_challenge.telegram_user_id::text limit 1;
  if v_crown_user is null then
    select black_crown_user_id into v_crown_user
      from public.black_crown_resolve_telegram_identity(v_challenge.telegram_user_id) limit 1;
  end if;
  if v_crown_user is null then return jsonb_build_object('ok',false,'reason','canonical_identity_unavailable'); end if;

  select black_crown_user_id into v_existing_web_user from public.black_crown_identities
   where provider='website_auth' and provider_subject=p_site_user_id limit 1;
  if v_existing_web_user is not null and v_existing_web_user<>v_crown_user then
    return jsonb_build_object('ok',false,'reason','canonical_identity_conflict');
  end if;

  insert into public.black_crown_identities(black_crown_user_id,provider,provider_subject,status,metadata,verified_at)
  values(v_crown_user,'website_auth',p_site_user_id,'active',jsonb_build_object('linked_via','telegram_one_time_code'),now())
  on conflict(provider,provider_subject) do update set
    status='active',verified_at=now(),updated_at=now(),
    metadata=coalesce(public.black_crown_identities.metadata,'{}'::jsonb)||jsonb_build_object('linked_via','telegram_one_time_code');
  update public.black_crown_identities set status='active',verified_at=coalesce(verified_at,now()),updated_at=now()
   where black_crown_user_id=v_crown_user and provider='telegram' and provider_subject=v_challenge.telegram_user_id::text;
  update public.black_crown_accounts set account_status='active',updated_at=now() where black_crown_user_id=v_crown_user;

  if v_existing_site.site_user_id is not null then
    v_event:='link_refreshed';
    update public.blackcrown_account_links set telegram_chat_id=v_challenge.telegram_chat_id,telegram_username=v_challenge.telegram_username,updated_at=now() where site_user_id=p_site_user_id;
  else
    insert into public.blackcrown_account_links(site_user_id,telegram_user_id,telegram_chat_id,telegram_username,status)
    values(p_site_user_id,v_challenge.telegram_user_id,v_challenge.telegram_chat_id,v_challenge.telegram_username,'active');
  end if;
  update public.blackcrown_telegram_link_challenges set consumed_at=now() where id=v_challenge.id;
  insert into public.blackcrown_account_link_events(site_user_id,telegram_user_id,event_type,metadata)
  values(p_site_user_id,v_challenge.telegram_user_id,v_event,jsonb_build_object('challenge_id',v_challenge.id,'black_crown_user_id',v_crown_user));
  insert into public.black_crown_identity_events(black_crown_user_id,event_type,provider,provider_subject_hash,metadata)
  values(v_crown_user,'website_identity_linked','website_auth',encode(extensions.digest(p_site_user_id,'sha256'),'hex'),jsonb_build_object('source','telegram_one_time_code'));

  select coalesce(array_agg(entitlement_key order by entitlement_key),array[]::text[]) into v_entitlements
    from public.blackcrown_entitlements where site_user_id=p_site_user_id and status='active' and valid_from<=now() and (valid_until is null or valid_until>now());
  v_premium:='bco_premium'=any(v_entitlements);
  return jsonb_build_object('ok',true,'linked',true,'premium',v_premium,'entitlements',to_jsonb(v_entitlements),'linked_at',now(),'black_crown_user_id',v_crown_user);
exception when unique_violation then return jsonb_build_object('ok',false,'reason','link_conflict');
end;
$function$;

create or replace function public.blackcrown_get_site_telegram_status(p_site_user_id text)
returns jsonb
language plpgsql
stable security definer
set search_path to 'public'
as $function$
declare
  v_link public.blackcrown_account_links%rowtype;
  v_entitlements text[]:=array[]::text[];
  v_premium boolean:=false;
  v_crown_user uuid;
begin
  if p_site_user_id is null or length(p_site_user_id)<1 or length(p_site_user_id)>160 or p_site_user_id !~ '^[A-Za-z0-9_.:@-]+$' then
    return jsonb_build_object('ok',false,'reason','invalid_site_user');
  end if;
  select * into v_link from public.blackcrown_account_links where site_user_id=p_site_user_id and status='active';
  if not found then return jsonb_build_object('ok',true,'linked',false,'premium',false,'entitlements','[]'::jsonb,'black_crown_user_id',null); end if;
  select black_crown_user_id into v_crown_user from public.black_crown_identities where provider='website_auth' and provider_subject=p_site_user_id limit 1;
  select coalesce(array_agg(entitlement_key order by entitlement_key),array[]::text[]) into v_entitlements
    from public.blackcrown_entitlements where site_user_id=p_site_user_id and status='active' and valid_from<=now() and (valid_until is null or valid_until>now());
  v_premium:='bco_premium'=any(v_entitlements);
  return jsonb_build_object('ok',true,'linked',true,'premium',v_premium,'entitlements',to_jsonb(v_entitlements),'linked_at',v_link.linked_at,'black_crown_user_id',v_crown_user);
end;
$function$;

-- Backfill only unambiguous active links. Never merge two canonical users implicitly.
do $backfill$
declare r record; v_crown_user uuid; v_existing_web_user uuid;
begin
  for r in select site_user_id,telegram_user_id from public.blackcrown_account_links where status='active' loop
    select black_crown_user_id into v_crown_user from public.black_crown_identities where provider='telegram' and provider_subject=r.telegram_user_id::text limit 1;
    if v_crown_user is null then continue; end if;
    select black_crown_user_id into v_existing_web_user from public.black_crown_identities where provider='website_auth' and provider_subject=r.site_user_id limit 1;
    if v_existing_web_user is null then
      insert into public.black_crown_identities(black_crown_user_id,provider,provider_subject,status,metadata,verified_at)
      values(v_crown_user,'website_auth',r.site_user_id,'active',jsonb_build_object('backfilled_from','blackcrown_account_links'),now());
      update public.black_crown_identities set status='active',updated_at=now() where black_crown_user_id=v_crown_user and provider='telegram' and provider_subject=r.telegram_user_id::text;
      update public.black_crown_accounts set account_status='active',updated_at=now() where black_crown_user_id=v_crown_user;
      insert into public.black_crown_identity_events(black_crown_user_id,event_type,provider,provider_subject_hash,metadata)
      values(v_crown_user,'website_identity_backfilled','website_auth',encode(extensions.digest(r.site_user_id,'sha256'),'hex'),jsonb_build_object('source','active_account_link'));
    end if;
  end loop;
end $backfill$;
