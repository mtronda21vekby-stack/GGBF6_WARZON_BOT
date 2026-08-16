# BLACK CROWN OPS — Phase 9 Production Readiness

## Mission

Prove persistent-storage connectivity when the Render process starts, without waiting for a player message and without creating synthetic player rows.

## Problem

A configured `SUPABASE_SERVICE_ROLE_KEY` and green GitHub CI prove code/config correctness, but they do not prove that the running Render process:

- picked up the latest `main`;
- received the server secret;
- can authenticate to the approved Supabase `GAME` project;
- can reach the expected PostgREST schema.

Previously, `build_store()` constructed the Supabase client lazily and made no network request until the first player storage operation.

## Startup probe

V9 adds a read-only persistent-primary probe.

`SupabaseStore.ping()` sends:

```text
HEAD /rest/v1/bco_players?select=chat_id&limit=1
X-BCO-Storage-Probe: startup-v9
```

Properties:

- HEAD only;
- no row insert/update/delete;
- no synthetic Telegram chat/user id;
- no profile/message content;
- service-role authentication is exercised;
- schema/table visibility is exercised.

## FastAPI lifecycle

During FastAPI lifespan startup:

1. if the active store exposes `probe_primary()`, it runs in a worker thread;
2. startup logs only success/failure + adapter/error class;
3. bot startup continues even when Supabase is temporarily unavailable because the existing memory fallback remains active;
4. normal shutdown cleanup is unchanged.

Memory-only deployments skip the probe.

## Readiness state

`ResilientStore.recovery_status()` now also exposes:

- `last_probe_ok`;
- `last_probe_at`;
- `probe_successes`;
- `probe_failures`.

`/health/details` surfaces these fields without credentials, Supabase URL or player content.

A failed probe marks readiness `degraded`, not dead. `/health` remains the simple liveness endpoint.

## Production verification

After Render deploys V9, Supabase API logs should contain the read-only HEAD request to `bco_players`. This lets operators distinguish:

- no new Render deploy / secret not loaded -> no startup probe observed;
- deployed but Supabase auth/network failure -> probe failure in readiness/logs;
- deployed and connected -> HEAD 2xx + `last_probe_ok=true`.

## Tests

V9 covers:

- Supabase probe uses HEAD, not mutation;
- probe carries no body/player data;
- successful primary probe updates readiness state;
- failed probe degrades without crashing;
- FastAPI lifespan actually invokes the storage probe.

No Supabase migration is required for V9.
