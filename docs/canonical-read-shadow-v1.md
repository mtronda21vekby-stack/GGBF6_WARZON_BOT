# BLACK CROWN Canonical Read Shadow v1

## Status

Phase 2C1 introduces a **read-only canonical parity probe**. It does not
switch product behavior away from legacy keys.

- Audited base `main`: `cbd5cdd68fad984e48bedadbf260c9cf1cbcc278`.
- Product release remains `44.0.0`.
- Website, Telegram Bot and Mini App presentation are unchanged.
- GAME is the only Supabase authority in scope.
- Legacy reads remain the value returned to the caller.
- Canonical primary reads remain disabled.

## Why this phase is separate

Phase 2A added canonical owner columns, backfill, conflict states and coverage.
Phase 2B added database-enforced canonical dual-write with a rollback flag.

A direct switch to canonical reads would still be premature because current
tables retain legacy uniqueness and lifecycle semantics. In particular,
multiple historical rows can legitimately project to one canonical account
until a later controlled consolidation step. Phase 2C1 measures parity before
any user-visible read authority changes.

## Runtime flow

For supported persistent read surfaces:

1. execute the existing legacy read;
2. deterministically sample the read according to server configuration;
3. resolve eligible canonical candidates through the server-only
   `black_crown_eligible_identity_candidates` contract;
4. when exactly one eligible account exists, query the same surface by
   `black_crown_user_id`;
5. compare normalized results without logging content or identity values;
6. emit content-free process telemetry;
7. return the legacy value regardless of the comparison outcome.

Supported surfaces:

- conversation messages;
- CROWN profile;
- summary;
- derived intelligence / Player Brain projection;
- recurring mistakes;
- episodes;
- training sessions;
- progression events.

Shadow lookup or comparison failure is isolated. It cannot convert a successful
legacy read into a user-visible error or memory fallback.

## Identity authority

The shadow layer never accepts `black_crown_user_id` from a browser, Mini App
payload, profile JSON, Telegram username or caller argument.

Canonical candidates are resolved from the Phase 2B server-only function using:

- provider: `telegram`;
- verified server-side Telegram subject;
- identity state: `active` or `provisional`;
- account state: `active` or `provisional`.

Zero candidates produce `identity_unresolved`. Multiple candidates produce
`identity_conflict`. Neither state performs a canonical product-table read.

The identity cache contains only the internal Telegram numeric key and canonical
UUID candidates in process memory. It is bounded, TTL-controlled and never
included in telemetry or health output. Negative results use a short TTL so a
newly resolved identity can become visible quickly.

## Parity outcomes

Telemetry distinguishes:

- `match`;
- `canonical_only`;
- `canonical_empty`;
- `canonical_superset`;
- `canonical_subset`;
- `mismatch`;
- `canonical_ambiguous`;
- `identity_unresolved`;
- `identity_conflict`;
- `identity_error`;
- `canonical_error`;
- `sample_skipped`.

Singleton profile rows are considered ambiguous when one canonical account has
multiple different values. Ambiguity never changes the returned value.

## Privacy and observability

`/health/details` already exposes `quality_telemetry.snapshot()`. This phase
adds a nested `quality.canonical_read_shadow` projection containing only:

- enabled state and sample rate;
- event/comparison counts;
- average shadow latency;
- aggregate item counts;
- surface counters;
- outcome counters;
- explicit `returns_legacy=true`;
- explicit `canonical_primary_enabled=false`.

It never contains:

- Telegram IDs;
- `black_crown_user_id`;
- profile values;
- prompts or answers;
- message content;
- transcript/audio;
- raw identity subjects;
- Supabase or OpenAI secrets.

Metrics are process-local in this phase. They are suitable for immediate
release observation and rollback decisions without adding a paid write on every
read. Durable aggregate parity telemetry can be added after the outcome model is
proven stable.

## Server configuration and rollback

Environment contract:

```text
CANONICAL_READ_SHADOW_ENABLED=true
CANONICAL_READ_SHADOW_SAMPLE_RATE=1.0
CANONICAL_READ_IDENTITY_CACHE_TTL_S=120
CANONICAL_READ_IDENTITY_NEGATIVE_CACHE_TTL_S=5
CANONICAL_READ_IDENTITY_CACHE_MAX_ENTRIES=10000
```

Immediate rollback:

```text
CANONICAL_READ_SHADOW_ENABLED=false
```

This restores the exact pre-Phase-2C read cost and behavior without schema
rollback, data mutation or deletion.

Reducing the sample rate is also non-destructive. Invalid numeric values fail at
normal settings validation during startup; runtime clamps sample rate and cache
bounds to safe ranges.

## Promotion gates for canonical-first reads

Canonical primary reads must remain disabled until all of the following are
demonstrated:

1. no identity conflicts or merge-pending states;
2. no unexplained singleton ambiguity;
3. parity is stable per surface;
4. canonical-only/superset outcomes are understood and intentional;
5. clear/reset/purge semantics are canonical-account safe;
6. entitlement and privacy lifecycle behavior is verified;
7. rollback can restore legacy reads without data loss;
8. Required Gate, Intelligence CI, Compatibility Contracts and CodeQL are green;
9. Render reports the exact merge SHA and health evidence.

A later Phase 2C2 PR may introduce canonical-first reads with legacy fallback.
This phase intentionally does not contain that switch.
