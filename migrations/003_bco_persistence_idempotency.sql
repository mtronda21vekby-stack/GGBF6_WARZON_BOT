-- BLACK CROWN OPS — Phase 8 persistence recovery idempotency
-- Backward-compatible: operation_id is nullable, so pre-v8 writers still work.

alter table public.bco_messages add column if not exists operation_id text;
alter table public.bco_episodes add column if not exists operation_id text;
alter table public.bco_training_sessions add column if not exists operation_id text;
alter table public.bco_progression_events add column if not exists operation_id text;

-- Regular UNIQUE indexes are intentional: PostgreSQL permits multiple NULLs,
-- while PostgREST can use operation_id directly as an on_conflict target.
create unique index if not exists bco_messages_operation_id_uidx
    on public.bco_messages(operation_id);
create unique index if not exists bco_episodes_operation_id_uidx
    on public.bco_episodes(operation_id);
create unique index if not exists bco_training_sessions_operation_id_uidx
    on public.bco_training_sessions(operation_id);
create unique index if not exists bco_progression_events_operation_id_uidx
    on public.bco_progression_events(operation_id);

create table if not exists public.bco_mistake_receipts (
    operation_id text primary key,
    chat_id bigint not null,
    mistake_key text not null,
    created_at timestamptz not null default now()
);
create index if not exists bco_mistake_receipts_chat_id_idx
    on public.bco_mistake_receipts(chat_id, created_at desc);

alter table public.bco_mistake_receipts enable row level security;
revoke all privileges on table public.bco_mistake_receipts from anon, authenticated;
grant select, insert, delete on table public.bco_mistake_receipts to service_role;

drop policy if exists bco_mistake_receipts_server_only on public.bco_mistake_receipts;
create policy bco_mistake_receipts_server_only
on public.bco_mistake_receipts
for all to anon, authenticated
using (false)
with check (false);

create or replace function public.bco_record_mistake_once(
    p_operation_id text,
    p_chat_id bigint,
    p_mistake_key text,
    p_label text,
    p_evidence jsonb default '{}'::jsonb
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    inserted_count integer := 0;
begin
    if p_operation_id is null or length(trim(p_operation_id)) < 8 then
        raise exception 'operation_id is required';
    end if;

    insert into public.bco_mistake_receipts(operation_id, chat_id, mistake_key)
    values (p_operation_id, p_chat_id, p_mistake_key)
    on conflict (operation_id) do nothing;

    get diagnostics inserted_count = row_count;
    if inserted_count = 0 then
        return false;
    end if;

    insert into public.bco_player_mistakes(chat_id, mistake_key, label, count, evidence)
    values (p_chat_id, p_mistake_key, p_label, 1, coalesce(p_evidence, '{}'::jsonb))
    on conflict (chat_id, mistake_key) do update
    set label = excluded.label,
        count = public.bco_player_mistakes.count + 1,
        last_seen = now(),
        evidence = coalesce(public.bco_player_mistakes.evidence, '{}'::jsonb) || coalesce(excluded.evidence, '{}'::jsonb);

    return true;
end;
$$;

revoke all on function public.bco_record_mistake_once(text, bigint, text, text, jsonb)
    from public, anon, authenticated;
grant execute on function public.bco_record_mistake_once(text, bigint, text, text, jsonb)
    to service_role;

-- Keep the existing full-player reset semantics complete: receipts contain
-- chat_id/mistake metadata and must disappear together with player data.
create or replace function public.bco_purge_player(p_chat_id bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.bco_messages where chat_id = p_chat_id;
    delete from public.bco_player_mistakes where chat_id = p_chat_id;
    delete from public.bco_mistake_receipts where chat_id = p_chat_id;
    delete from public.bco_episodes where chat_id = p_chat_id;
    delete from public.bco_training_sessions where chat_id = p_chat_id;
    delete from public.bco_progression_events where chat_id = p_chat_id;
    delete from public.bco_players where chat_id = p_chat_id;
end;
$$;

revoke all on function public.bco_purge_player(bigint) from public, anon, authenticated;
grant execute on function public.bco_purge_player(bigint) to service_role;

-- Receipts are tiny metadata rows. A later maintenance job may delete old
-- receipts only after the chosen replay horizon has elapsed.
