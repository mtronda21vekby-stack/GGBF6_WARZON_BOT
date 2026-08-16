# BLACK CROWN OPS — Phase 2 Persistent Player Intelligence

## Scope

Phase 2 turns the v1 storage interfaces into a real optional persistence layer and adds evidence-based player memory. It remains safe to run with no external database configured: `STORAGE_BACKEND=auto` falls back to the in-process store.

## Runtime storage modes

- `STORAGE_BACKEND=auto` (default): Supabase is used only when both server-side Supabase values exist; otherwise memory.
- `STORAGE_BACKEND=memory`: force legacy in-process behavior.
- `STORAGE_BACKEND=supabase`: request persistent Supabase storage; incomplete configuration degrades to memory rather than preventing bot startup.

Server-only environment variables:

```text
STORAGE_BACKEND=auto
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<server secret>
SUPABASE_SCHEMA=public
STORAGE_TIMEOUT_S=8
```

Never put `SUPABASE_SERVICE_ROLE_KEY` in Mini App JavaScript, GitHub, Telegram messages or logs.

Before enabling Supabase, apply:

`migrations/001_player_intelligence.sql`

The migration enables RLS and exposes write RPCs only to `service_role`. The browser/Mini App has no direct table access.

## Persistent namespaces

- working conversation messages;
- stable player profile;
- deterministic long-term summary;
- derived analytics;
- recurring mistakes with evidence counts;
- episodic coaching signals;
- training sessions;
- progression/match-report events.

## Evidence rules

Player memory is deliberately conservative. Phase 2 stores profile facts only when explicitly stated by the player (for example K/D, rank or an explicitly framed goal). Repeated tactical mistakes are tagged only when the user's text contains direct evidence. Numeric aim/movement/decision scores are not invented.

No extra LLM request is made merely to update memory.

## Trust boundary

`ProfileService` signs server-created request context with an in-process HMAC token. Telegram requests and verified Mini App requests receive server-generated profile context. A client-supplied profile cannot forge the token and therefore cannot mutate persistent player intelligence through `ConversationService`.

The token is transient, is never persisted and is excluded from prompts.

## Failover behavior

When Supabase is active, writes are mirrored to an in-process fallback. Remote read/write failures are logged by method/error class only; the bot continues on the memory mirror. Writes made only during a remote outage are not yet backfilled automatically — queued reconciliation is a later hardening task.

## Reset semantics

- **Clear memory**: clears working conversation history only.
- **Reset** through `ProfileService.reset`: purges profile, working memory, summaries, mistakes, episodes, training and progression when the backend implements `purge_player`.

## Phase 2 output used by the brain

The prompt may receive:

- `memory_summary`;
- top recurring mistakes + counts;
- recent training events;
- recent progression reports;
- derived trend evidence.

These are historical evidence only. The AI is explicitly forbidden to fabricate improvement when the stored evidence is insufficient.

## Next hardening

After the stacked PR is reviewed and persistence is configured:

1. add queued remote-outage reconciliation;
2. add retention controls and user-facing data export/delete;
3. add richer explicit post-match forms in Mini App;
4. calibrate derived scores only after sufficient real observations;
5. proceed to Phase 3 Live Game Intelligence.
