-- BLACK CROWN ADMIN COMMAND CENTER v1
-- Privacy-safe server-only telemetry for accurate period reporting.
-- No browser/client role receives direct access.

create table if not exists public.bco_user_activity_daily (
  activity_date date not null default current_date,
  telegram_user_id bigint not null,
  black_crown_user_id uuid references public.black_crown_accounts(black_crown_user_id) on delete set null,
  update_count bigint not null default 0,
  message_count bigint not null default 0,
  voice_count bigint not null default 0,
  miniapp_count bigint not null default 0,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  primary key (activity_date, telegram_user_id)
);

create index if not exists bco_user_activity_daily_crown_idx
  on public.bco_user_activity_daily(activity_date, black_crown_user_id)
  where black_crown_user_id is not null;

alter table public.bco_user_activity_daily enable row level security;
revoke all on public.bco_user_activity_daily from public, anon, authenticated;
grant select, insert, update on public.bco_user_activity_daily to service_role;

create or replace function public.bco_record_user_activity(
  p_user_id bigint,
  p_chat_id bigint,
  p_language text default null,
  p_surface text default 'telegram',
  p_is_message boolean default false,
  p_is_voice boolean default false,
  p_is_miniapp boolean default false
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
declare
  v_crown_user uuid;
begin
  if p_user_id is null or p_user_id <= 0 then
    raise exception using errcode='22023', message='invalid activity user';
  end if;

  insert into public.bco_user_activity(
    telegram_user_id, telegram_chat_id, first_seen_at, last_seen_at,
    last_language, last_surface, update_count, message_count, voice_count, miniapp_count
  ) values (
    p_user_id, p_chat_id, now(), now(), left(coalesce(p_language,''),16), left(coalesce(p_surface,'telegram'),32),
    1, case when p_is_message then 1 else 0 end,
    case when p_is_voice then 1 else 0 end,
    case when p_is_miniapp then 1 else 0 end
  )
  on conflict (telegram_user_id) do update set
    telegram_chat_id = excluded.telegram_chat_id,
    last_seen_at = now(),
    last_language = case when excluded.last_language <> '' then excluded.last_language else bco_user_activity.last_language end,
    last_surface = excluded.last_surface,
    update_count = bco_user_activity.update_count + 1,
    message_count = bco_user_activity.message_count + case when p_is_message then 1 else 0 end,
    voice_count = bco_user_activity.voice_count + case when p_is_voice then 1 else 0 end,
    miniapp_count = bco_user_activity.miniapp_count + case when p_is_miniapp then 1 else 0 end;

  select black_crown_user_id into v_crown_user
  from public.bco_user_activity
  where telegram_user_id = p_user_id;

  insert into public.bco_user_activity_daily(
    activity_date, telegram_user_id, black_crown_user_id,
    update_count, message_count, voice_count, miniapp_count,
    first_seen_at, last_seen_at
  ) values (
    current_date, p_user_id, v_crown_user,
    1, case when p_is_message then 1 else 0 end,
    case when p_is_voice then 1 else 0 end,
    case when p_is_miniapp then 1 else 0 end,
    now(), now()
  )
  on conflict (activity_date, telegram_user_id) do update set
    black_crown_user_id = coalesce(bco_user_activity_daily.black_crown_user_id, excluded.black_crown_user_id),
    update_count = bco_user_activity_daily.update_count + 1,
    message_count = bco_user_activity_daily.message_count + case when p_is_message then 1 else 0 end,
    voice_count = bco_user_activity_daily.voice_count + case when p_is_voice then 1 else 0 end,
    miniapp_count = bco_user_activity_daily.miniapp_count + case when p_is_miniapp then 1 else 0 end,
    last_seen_at = now();
end;
$function$;

revoke all on function public.bco_record_user_activity(bigint,bigint,text,text,boolean,boolean,boolean)
  from public, anon, authenticated;
grant execute on function public.bco_record_user_activity(bigint,bigint,text,text,boolean,boolean,boolean)
  to service_role;

create or replace function public.bco_admin_dashboard_v1()
returns table(payload jsonb)
language sql
security definer
set search_path = public, pg_temp
as $function$
  select jsonb_build_object(
    'schema', 'bco-admin-dashboard-v1',
    'generated_at', now(),
    'users', jsonb_build_object(
      'tracked_telegram', (select count(*) from public.bco_user_activity),
      'unified_known', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity),
      'canonical_accounts', (select count(*) from public.black_crown_accounts where account_status <> 'disabled'),
      'active_24h', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity where last_seen_at >= now() - interval '24 hours'),
      'active_7d', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity where last_seen_at >= now() - interval '7 days'),
      'active_30d', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity where last_seen_at >= now() - interval '30 days'),
      'new_24h', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity where first_seen_at >= now() - interval '24 hours'),
      'new_7d', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity where first_seen_at >= now() - interval '7 days')
    ),
    'activity', jsonb_build_object(
      'daily_timezone', 'UTC',
      'total_updates', (select coalesce(sum(update_count),0) from public.bco_user_activity),
      'total_messages', (select coalesce(sum(message_count),0) from public.bco_user_activity),
      'total_voice', (select coalesce(sum(voice_count),0) from public.bco_user_activity),
      'total_miniapp', (select coalesce(sum(miniapp_count),0) from public.bco_user_activity),
      'today_updates', (select coalesce(sum(update_count),0) from public.bco_user_activity_daily where activity_date = current_date),
      'today_messages', (select coalesce(sum(message_count),0) from public.bco_user_activity_daily where activity_date = current_date),
      'today_voice', (select coalesce(sum(voice_count),0) from public.bco_user_activity_daily where activity_date = current_date),
      'today_miniapp', (select coalesce(sum(miniapp_count),0) from public.bco_user_activity_daily where activity_date = current_date),
      'today_miniapp_users', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity_daily where activity_date = current_date and miniapp_count > 0),
      'week_updates', (select coalesce(sum(update_count),0) from public.bco_user_activity_daily where activity_date >= current_date - 6),
      'week_messages', (select coalesce(sum(message_count),0) from public.bco_user_activity_daily where activity_date >= current_date - 6),
      'week_voice', (select coalesce(sum(voice_count),0) from public.bco_user_activity_daily where activity_date >= current_date - 6),
      'week_miniapp', (select coalesce(sum(miniapp_count),0) from public.bco_user_activity_daily where activity_date >= current_date - 6),
      'week_miniapp_users', (select count(distinct coalesce(black_crown_user_id::text, 'tg:' || telegram_user_id::text)) from public.bco_user_activity_daily where activity_date >= current_date - 6 and miniapp_count > 0),
      'daily_ledger_started_at', (select min(activity_date) from public.bco_user_activity_daily),
      'daily_coverage_days', (select count(distinct activity_date) from public.bco_user_activity_daily)
    ),
    'identity', jsonb_build_object(
      'accounts', (select count(*) from public.black_crown_accounts),
      'identities', (select count(*) from public.black_crown_identities where status in ('active','provisional')),
      'resolved', (select count(*) from public.black_crown_ownership_migration_state where state='resolved'),
      'unresolved', (select count(*) from public.black_crown_ownership_migration_state where state='unresolved'),
      'conflict', (select count(*) from public.black_crown_ownership_migration_state where state='conflict'),
      'merge_pending', (select count(*) from public.black_crown_ownership_migration_state where state='merge_pending'),
      'dual_write', coalesce((select enabled from public.black_crown_ownership_runtime_flags where flag_key='canonical_dual_write'),false),
      'shadow_read', coalesce((select enabled from public.black_crown_ownership_runtime_flags where flag_key='canonical_shadow_read'),false)
    ),
    'premium', jsonb_build_object(
      'active_accounts', (select count(distinct coalesce(black_crown_user_id::text, 'site:' || site_user_id)) from public.blackcrown_entitlements where status='active' and valid_from <= now() and (valid_until is null or valid_until > now()))
    ),
    'intel', jsonb_build_object(
      'snapshots', (select count(*) from public.bco_game_intel_snapshots),
      'changes', (select count(*) from public.bco_game_intel_changes),
      'latest_snapshot_at', (select max(fetched_at) from public.bco_game_intel_snapshots),
      'latest_change_at', (select max(created_at) from public.bco_game_intel_changes)
    )
  );
$function$;

revoke all on function public.bco_admin_dashboard_v1() from public, anon, authenticated;
grant execute on function public.bco_admin_dashboard_v1() to service_role;
