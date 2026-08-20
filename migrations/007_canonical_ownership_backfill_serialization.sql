-- BLACK CROWN canonical ownership backfill serialization
--
-- Every backfill transaction starts by inserting one migration-run row. This
-- trigger takes a row lock before that insert completes, serializing concurrent
-- service-role runs until commit/rollback. Sequential retries remain idempotent,
-- while merge_pending audit-event creation cannot race with another backfill.

create table if not exists public.black_crown_ownership_migration_lock (
  lock_key text primary key,
  created_at timestamptz not null default now(),
  constraint black_crown_ownership_lock_key_check
    check (lock_key = 'bco-canonical-owner-v1')
);

insert into public.black_crown_ownership_migration_lock (lock_key)
values ('bco-canonical-owner-v1')
on conflict (lock_key) do nothing;

alter table public.black_crown_ownership_migration_lock enable row level security;
revoke all on table public.black_crown_ownership_migration_lock
  from public, anon, authenticated;
grant select, insert, update, delete
  on table public.black_crown_ownership_migration_lock
  to service_role;

do $policy$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'black_crown_ownership_migration_lock'
      and policyname = 'black_crown_ownership_lock_browser_deny'
  ) then
    create policy black_crown_ownership_lock_browser_deny
      on public.black_crown_ownership_migration_lock
      for all
      to anon, authenticated
      using (false)
      with check (false);
  end if;
end
$policy$;

create or replace function public.black_crown_serialize_ownership_migration_run()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $function$
begin
  perform 1
  from public.black_crown_ownership_migration_lock
  where lock_key = 'bco-canonical-owner-v1'
  for update;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'canonical ownership migration lock is unavailable';
  end if;

  return new;
end;
$function$;

revoke all on function public.black_crown_serialize_ownership_migration_run()
  from public, anon, authenticated;
grant execute on function public.black_crown_serialize_ownership_migration_run()
  to service_role;

do $trigger$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'black_crown_ownership_runs_serialize'
      and tgrelid = 'public.black_crown_ownership_migration_runs'::regclass
      and not tgisinternal
  ) then
    create trigger black_crown_ownership_runs_serialize
      before insert
      on public.black_crown_ownership_migration_runs
      for each row
      execute function public.black_crown_serialize_ownership_migration_run();
  end if;
end
$trigger$;
