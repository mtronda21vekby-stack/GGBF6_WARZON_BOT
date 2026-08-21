# BLACK CROWN Canonical Ownership Dual-Read v1

## Status

Phase 2C installs a **staged, disabled-by-default** canonical-first read path. It does not remove a legacy key and does not change Website or Telegram presentation.

- Audited base `main`: `cbd5cdd68fad984e48bedadbf260c9cf1cbcc278`.
- Product release remains `44.0.0`.
- GAME is the only Supabase project in scope.
- Database flag at migration install: `canonical_dual_read=false`.
- Application capability can also be disabled with `CANONICAL_READ_CAPABILITY_ENABLED=0`.
- Legacy `chat_id` / `telegram_user_id` remain mandatory and are the exact fallback authority.

The database flag is intentionally independent from `canonical_dual_write`. Operators can disable canonical reads without stopping canonical projection on new writes.

## Read authority

A storage caller supplies only the verified Telegram subject already accepted by the legacy API. It never supplies `black_crown_user_id`.

The server-only flow is:

1. read the service-role `canonical_dual_read` flag;
2. resolve the Telegram provider subject through `black_crown_resolve_read_owner`;
3. require exactly one eligible canonical account;
4. query product data by `black_crown_user_id`;
5. fall back to the exact legacy subject when canonical evidence is insufficient.

`black_crown_resolve_read_owner` is read-only. It does not create an account, create an identity, merge accounts, transfer Premium or persist a raw provider subject.

## Fail-closed fallback matrix

| Condition | Read behavior | Telemetry |
|---|---|---|
| Application capability disabled | legacy key | `capability_disabled` |
| Database flag absent or disabled | legacy key | stable control state only |
| Flag lookup error | legacy key | exception class only |
| No eligible canonical identity | legacy key | `identity_unresolved` |
| More than one canonical candidate | legacy key | `identity_conflict` |
| Canonical query error | legacy key | `canonical_query_error` |
| Canonical query returns no rows | legacy key | `canonical_miss` |
| Singleton surface returns multiple rows | legacy key | `canonical_ambiguous` |
| Exactly one owner and valid result | canonical owner | `canonical_hit` |

No canonical owner UUID, Telegram subject, profile payload, transcript, history content or database operator reason is emitted in logs or `/health/details` telemetry.

## Covered read surfaces

Canonical-first routing is implemented for:

- conversation history;
- CROWN Profile;
- profile summary;
- derived Player Brain intelligence;
- recurring mistake statistics;
- episodes and After Action evidence;
- training sessions;
- progression events;
- storage statistics/counts.

Collection surfaces can aggregate rows projected to one canonical account. Singleton surfaces such as profile/summary/derived intelligence refuse to choose between multiple canonical rows and fall back to the current legacy subject instead of silently merging data.

## Destructive lifecycle boundary

Phase 2C does **not** broaden destructive operations:

- `clear` remains scoped to the legacy chat;
- `reset_profile` remains scoped to the legacy chat;
- `purge_player` remains the existing legacy server RPC.

Therefore the database flag remains disabled at migration install. Enabling canonical-first reads requires a separate operational decision after parity evidence and before any promise that a legacy-scoped clear removes all canonical conversation history. Canonical lifecycle semantics will be delivered in a separate narrow phase.

## Current GAME baseline

Fresh verification after Phase 2B:

- `canonical_dual_write=true`;
- 11/11 ownership triggers installed;
- 3 resolved mappings;
- 2 unresolved mappings;
- 0 conflicts;
- 0 merge-pending links;
- messages: 172/172 projected;
- episodes: 5/5 projected;
- progression: 3/3 projected;
- training: 1/1 projected;
- account link and link event: fully projected;
- profiles: 1/2 projected;
- activity: 1/2 projected.

The unresolved historical subject remains legacy-only. Phase 2C does not manufacture an account to improve a percentage.

## Transactional GAME validation

Migration 009 was executed against GAME inside `BEGIN ... ROLLBACK` before opening the PR.

The dry-run proved:

- runtime schema advanced transactionally to `bco-canonical-owner-v3`;
- canonical read schema reported `bco-canonical-read-v1`;
- `canonical_dual_read` could be enabled and restored independently;
- `canonical_dual_write` remained enabled;
- all 11 expected dual-write triggers remained installed;
- an existing active Telegram identity resolved to exactly one owner;
- a missing identity resolved to `unresolved` with zero candidates;
- browser EXECUTE grants on the read resolver were zero;
- no raw provider subject or owner UUID was returned as audit evidence;
- product row counts remained 2 profiles, 172 messages, 5 episodes, 3 progression events, 1 training session, 2 activity rows and 0 entitlements.

Post-rollback verification proved zero residue:

- no `canonical_dual_read` flag row;
- no `black_crown_resolve_read_owner` function;
- runtime status restored to `bco-canonical-owner-v2`;
- no Phase 2C columns remained in the status view;
- `canonical_dual_write` remained enabled;
- all product row counts were unchanged.

## Privacy-safe readiness

`/health/details` reports:

- read schema version;
- application capability state;
- database flag state;
- active mode: `legacy` or `canonical_first`;
- flag update timestamp;
- last control error class;
- canonical hit/miss/ambiguity/query-error counters;
- fallback counters;
- per-table outcome counts.

It does not expose the service-role flag reason, owner UUIDs, provider subjects or row contents.

## Rollout and rollback

Safe rollout sequence:

1. merge application and migration with the database flag disabled;
2. deploy and verify exact Render SHA;
3. apply migration 009 to GAME;
4. verify service-role grants, status view and resolved/unresolved behavior;
5. keep production in legacy mode while observing health and storage stability;
6. implement canonical lifecycle semantics in a separate phase;
7. enable `canonical_dual_read` with a controlled service-role operation;
8. verify canonical hits and fallback rates before reducing any compatibility path.

Immediate rollback:

```sql
select public.black_crown_set_ownership_runtime_flag(
  'canonical_dual_read',
  false,
  'incident reference'
);
```

This changes only the read selector. It does not delete or rewrite canonical projections, legacy rows, Player Brain history, entitlements, accounts or audit evidence.
