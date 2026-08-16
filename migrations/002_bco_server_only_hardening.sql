-- BLACK CROWN OPS — server-only hardening for persistent player intelligence
-- Browser/Mini App roles must never access bco_* persistence tables directly.

revoke all privileges on table public.bco_players from anon, authenticated;
revoke all privileges on table public.bco_messages from anon, authenticated;
revoke all privileges on table public.bco_player_mistakes from anon, authenticated;
revoke all privileges on table public.bco_episodes from anon, authenticated;
revoke all privileges on table public.bco_training_sessions from anon, authenticated;
revoke all privileges on table public.bco_progression_events from anon, authenticated;

revoke all privileges on sequence public.bco_messages_id_seq from anon, authenticated;
revoke all privileges on sequence public.bco_episodes_id_seq from anon, authenticated;
revoke all privileges on sequence public.bco_training_sessions_id_seq from anon, authenticated;
revoke all privileges on sequence public.bco_progression_events_id_seq from anon, authenticated;

grant select, insert, update, delete on table public.bco_players to service_role;
grant select, insert, update, delete on table public.bco_messages to service_role;
grant select, insert, update, delete on table public.bco_player_mistakes to service_role;
grant select, insert, update, delete on table public.bco_episodes to service_role;
grant select, insert, update, delete on table public.bco_training_sessions to service_role;
grant select, insert, update, delete on table public.bco_progression_events to service_role;

grant usage, select on sequence public.bco_messages_id_seq to service_role;
grant usage, select on sequence public.bco_episodes_id_seq to service_role;
grant usage, select on sequence public.bco_training_sessions_id_seq to service_role;
grant usage, select on sequence public.bco_progression_events_id_seq to service_role;

create policy bco_players_server_only
on public.bco_players
for all to anon, authenticated
using (false)
with check (false);

create policy bco_messages_server_only
on public.bco_messages
for all to anon, authenticated
using (false)
with check (false);

create policy bco_player_mistakes_server_only
on public.bco_player_mistakes
for all to anon, authenticated
using (false)
with check (false);

create policy bco_episodes_server_only
on public.bco_episodes
for all to anon, authenticated
using (false)
with check (false);

create policy bco_training_sessions_server_only
on public.bco_training_sessions
for all to anon, authenticated
using (false)
with check (false);

create policy bco_progression_events_server_only
on public.bco_progression_events
for all to anon, authenticated
using (false)
with check (false);
