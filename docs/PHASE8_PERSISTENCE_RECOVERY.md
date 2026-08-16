# BLACK CROWN OPS — Phase 8 Persistence Recovery

## Mission

Recover writes after transient Supabase/PostgREST outages without taking down Telegram and without duplicating player intelligence after ambiguous network timeouts.

## Failure model

A network timeout does **not** prove that PostgreSQL did not commit the write. Blind retry can therefore create duplicate messages/events or increment a recurring mistake twice.

Phase 8 solves this with stable per-write `operation_id` values plus database idempotency primitives.

## Recovery flow

```text
write request
    ↓
mirror to in-process memory
    ↓
primary Supabase write with operation_id
    ├─ success → done
    └─ failure/timeout → bounded FIFO outbox
                              ↓
                    later read/write/close
                              ↓
                    replay oldest first
                              ↓
                    Supabase idempotency
```

If an old write cannot replay, later writes remain queued behind it so destructive/stateful ordering such as `clear → add` is preserved.

## Database migration

`migrations/003_bco_persistence_idempotency.sql` adds nullable `operation_id` columns and unique indexes to:

- `bco_messages`
- `bco_episodes`
- `bco_training_sessions`
- `bco_progression_events`

Legacy/pre-v8 writes remain valid because NULL operation IDs are allowed.

Recurring mistakes use a separate `bco_mistake_receipts` table and `bco_record_mistake_once(...)` RPC. The receipt and mistake increment run in the same PostgreSQL transaction, so replaying the same operation ID does not increment twice.

Full player purge also deletes mistake receipts because they contain player-linked metadata (`chat_id`).

## Append idempotency

For append tables, V8 writes with:

```text
operation_id=<stable UUID>
on_conflict=operation_id
Prefer: resolution=ignore-duplicates
```

If the first HTTP response is lost after commit, replay becomes a no-op instead of a duplicate row.

## State/deletion operations

Profile patch, summary, derived intelligence and delete/purge operations are replayed FIFO. Their resulting state is idempotent, and ordering is preserved within the process outbox.

## Important durability boundary

The V8 outbox is intentionally **process-local** and bounded. It recovers transient remote outages while the current Render process stays alive.

It does **not** claim to survive:

- container/process restart;
- host loss;
- forced deployment while writes are still pending.

A future durable queue would require persistent local storage or another external service. V8 does not introduce either dependency.

## Capacity controls

```text
STORAGE_OUTBOX_MAX=500
STORAGE_REPLAY_BATCH=50
```

When the queue is full, the text bot still uses its in-memory fallback, but the overflow is counted as `outbox_dropped` and logged. BLACK CROWN does not pretend those writes became durable remotely.

## Read consistency

When queued writes exist:

1. the store attempts a FIFO replay batch;
2. if anything remains pending, reads use the in-memory mirror rather than stale Supabase state;
3. after successful recovery, reads return to the primary backend.

## Observability

`/health/details` exposes privacy-safe recovery metadata:

- primary availability;
- pending write count;
- replayed count;
- dropped count;
- last primary error **class only**;
- configured outbox capacity.

No queued arguments, message text, profile values, secrets or API URLs are exposed.

## Additional persistence fix

Supabase `list_episodes()` now flattens the JSON `data` payload into the same event shape returned by `InMemoryStore`. This keeps VOD/Command Center consumers backend-independent.

## Tests

Failure-injection tests cover:

- timeout after a message was actually committed;
- clear → add ordering through a total outage;
- exactly-once recurring mistake replay;
- PostgREST `operation_id` conflict behavior;
- once-only recurring mistake RPC routing;
- normalized persistent VOD episode reads.

## Security

`bco_mistake_receipts` is server-only:

- RLS enabled;
- no anon/authenticated privileges;
- explicit deny policy;
- service_role access only;
- once-only RPC executable only by service_role.
