# BLACK CROWN Canonical Read Shadow v1

## Scope

Phase 2C adds comparison-only canonical reads after Phase 2B dual-write. It does
not switch product read authority and does not delete or relax any legacy key.

The established `chat_id` value remains the value returned for:

- conversation history;
- profile, summary and derived Player Brain intelligence;
- recurring mistakes;
- episodes;
- training sessions;
- progression events.

Canonical rows are sampled only to measure migration parity. A match, mismatch,
unresolved identity, ambiguity or shadow failure never changes the user-visible
value.

## Concurrent-agent integration

Another agent added the initial `CanonicalReadShadowStore` and content-free
`QualityTelemetry` counters to the same feature branch. This integration keeps
that implementation and adds the missing production controls around it rather
than replacing the newer files with an older copy.

## Authority and privacy

Canonical owner candidates are resolved through the existing Phase 2B
service-role function `black_crown_eligible_identity_candidates`. The browser,
Mini App and Telegram payload cannot submit `black_crown_user_id` as authority.

The shadow system records only:

- surface name;
- outcome classification;
- latency;
- legacy/canonical item counts;
- aggregate comparison totals.

It does not record prompts, message content, profile values, Telegram IDs,
canonical IDs, initData, transcripts, tokens or secrets. The bounded identity
cache is process-local and is never logged or exposed by readiness.

## Independent controls

Two database flags are independent:

- `canonical_dual_write` controls future owner projection;
- `canonical_shadow_read` controls comparison-only reads.

Immediate database rollback:

```sql
select public.black_crown_set_ownership_runtime_flag(
  'canonical_shadow_read',
  false,
  'incident reference and operator reason'
);
```

When disabled, every covered method performs one established legacy read. The
dual-write flag, existing canonical projections and user data are unchanged.

Process-local controls:

```text
CANONICAL_READ_SHADOW_ENABLED=1
CANONICAL_READ_SHADOW_SAMPLE_RATE=0.10
CANONICAL_READ_SHADOW_FLAG_TTL_S=30
CANONICAL_READ_SHADOW_IDENTITY_TTL_S=120
CANONICAL_READ_SHADOW_NEGATIVE_TTL_S=5
CANONICAL_READ_SHADOW_CACHE_MAX_ENTRIES=10000
```

The default sample rate is intentionally 10% to limit additional database
latency during the observation window. Sampling is deterministic by legacy
subject and surface.

## Failure behavior

The control and comparison layers fail closed to the established read:

- database flag lookup error -> legacy only;
- shadow flag disabled -> legacy only;
- identity lookup error -> legacy only;
- no identity candidate -> legacy only;
- multiple candidates -> legacy only;
- canonical query error -> legacy only;
- canonical ambiguity -> legacy only;
- mismatch -> legacy only.

Shadow failures are absorbed inside the wrapper and are not converted into
persistent-primary failures or recovery-outbox writes.

## Canonical identity through resilient storage

Phase 2C also exposes the existing server identity resolver through
`PersistentResilientStore`. Before this change, `ProfileService` received the
resilient wrapper while the resolver existed only on the inner Supabase adapter.
The memory fallback returns an empty projection and never manufactures an
account.

This repairs canonical identity projection across Bot and trusted Mini App
contexts without changing their profile mutation contract.

## Readiness

`/health/details` already publishes `quality_telemetry.snapshot()`. The canonical
block now includes:

- local enabled state;
- database enabled state;
- sample rate;
- sanitized control reason and check timestamp;
- control error count;
- comparison totals and outcomes;
- aggregate surfaces;
- `read_authority=legacy`;
- `canonical_returned_to_callers=false`.

No identity or player payload can enter this response.

The service-role database view
`black_crown_canonical_read_runtime_status` reports the two independent flags
and aggregate migration-state counts.

## Promotion boundary

Canonical-first reads remain prohibited until a separate phase proves sustained
parity, acceptable latency, sufficient ownership coverage, explicit semantics
for multi-identity accounts, zero unexplained conflicts, rollback, and
cross-client behavioral synchronization.
