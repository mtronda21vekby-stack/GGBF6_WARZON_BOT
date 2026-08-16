# BLACK CROWN OPS — Phase 10 Production Deployment Gate

## Mission

Stop treating a green GitHub merge as proof that Render is running the new release.

Phase 10 adds an explicit public release contract to `/health/details` and a GitHub Actions production gate that waits for the real Render service after every push to `main`.

## Release contract

`app/release.py` defines:

```text
APP_VERSION=10.0.0
RELEASE_CONTRACT=bco-aaa-v10
```

FastAPI uses the same version, and `/health/details` returns:

```json
{
  "release": {
    "version": "10.0.0",
    "contract": "bco-aaa-v10"
  }
}
```

No Git SHA, secret or infrastructure credential is exposed.

## Production gate

After the normal `test` job succeeds on a push to `main`, the `production-smoke` job polls:

```text
https://ggbf6-warzon-bot.onrender.com/health/details
```

for up to 10 minutes.

The deployment is accepted only when all of these are true:

- HTTP 200;
- release version matches the checked-out repository release contract;
- readiness status is `ready`;
- `persistent_memory_configured=true`;
- persistent primary reports `last_probe_ok=true`;
- persistent primary reports `primary_available=true`.

This verifies both Render rollout and the Supabase startup probe. A stale Render release cannot pass just because `/health` returns 200.

## Failure meaning

A red `production-smoke` is diagnostic evidence, not a bot code crash.

Examples:

- old/missing release version → Render has not rolled out the current `main` yet;
- persistent config false → server-side Supabase configuration was not loaded by the running service;
- startup probe false → running service cannot authenticate/reach the expected Supabase schema;
- endpoint unreachable → Render service/DNS/startup is unavailable from the GitHub runner.

The normal unit/integration test job remains separate, so application regressions and deployment failures are distinguishable.

## Safety

- no deploy hook secret is required;
- no Render API credential is committed;
- no Supabase service-role key enters GitHub Actions;
- the gate only reads the public readiness endpoint;
- `/health` liveness behavior is unchanged.
