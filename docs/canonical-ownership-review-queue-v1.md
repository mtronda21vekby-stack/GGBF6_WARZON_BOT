# BLACK CROWN Canonical Ownership Review Queue v1

## Status

Phase 2D adds a privacy-safe, service-role-only review queue for unresolved or conflicting canonical ownership evidence. It does **not** resolve ownership.

- Audited base `main`: `7404cacd56597a202f1d998342e0874ec5acac36`.
- Product release remains `44.0.0`.
- GAME is the only Supabase project in scope.
- Review workflow flag at migration install: `ownership_resolution_review=false`.
- Legacy product reads remain authoritative.
- Canonical shadow comparison remains non-authoritative.
- No Website, Telegram Bot, Mini App or Voice presentation is changed.

The queue exists to make unresolved ownership visible, reviewable and auditable without manufacturing an account mapping or silently merging identities.

## Non-authority contract

This phase has no API capable of applying ownership.

It cannot:

- create a `black_crown_account`;
- create or activate a `black_crown_identity`;
- write `black_crown_user_id` to product state;
- merge Website and Telegram accounts;
- transfer or grant Premium;
- mark an ownership case `resolved`;
- delete legacy Player Brain, history, progression or analytics;
- store a raw Telegram ID, Website user ID, chat ID or site user ID.

The only case states are:

- `open`;
- `blocked`;
- `awaiting_confirmation`;
- `superseded`.

`resolved` is deliberately absent.

Every case row has database constraints fixing these fields to `false`:

- `automatic_resolution_allowed`;
- `owner_write_allowed`;
- `entitlement_transfer_allowed`.

## Privacy model

The queue groups existing non-resolved migration evidence by:

- provider code;
- SHA-256 legacy-subject hash.

It stores or exposes only:

- the subject hash;
- affected product scopes;
- source migration states;
- aggregate legacy row count;
- internal candidate UUID array in the service-only base table;
- candidate count in the queue view;
- stable risk flags;
- whether a proposed owner exists;
- confirmation method/state;
- revision and timestamps.

The queue view does **not** project candidate account UUIDs or the proposed account UUID. Event actors are represented only by a 64-character SHA-256 reference hash.

Current unresolved historical projections are represented without returning their raw provider subjects. This phase does not infer that two hashes belong to the same person and does not create an account to improve coverage.

## Staged review switch

Migration install creates:

```text
ownership_resolution_review = false
```

Case refresh is allowed while the switch is disabled because it only rebuilds privacy-safe review evidence. Proposal and cancellation RPCs fail closed until the switch is explicitly enabled by service role.

Dedicated control:

```sql
select public.black_crown_set_ownership_review_enabled(
  true,
  'controlled review reference'
);
```

Immediate rollback:

```sql
select public.black_crown_set_ownership_review_enabled(
  false,
  'incident reference'
);
```

Disabling this switch prevents new proposal/cancel operations. It does not change dual-write, shadow reads, product rows, accounts, identities or entitlements.

## Refresh contract

`black_crown_refresh_ownership_resolution_cases()` is service-role-only and transactionally serialized with a PostgreSQL advisory lock.

It:

1. reads only non-resolved rows from `black_crown_ownership_migration_state`;
2. groups evidence by provider and hashed subject;
3. aggregates affected scopes and source states;
4. creates `open` cases for unresolved evidence;
5. creates `blocked` cases for conflict or merge-pending evidence;
6. preserves an awaiting-confirmation proposal only while all source evidence remains identical;
7. cancels the proposal automatically when source evidence changes;
8. marks disappeared source evidence `superseded`;
9. never updates product ownership.

Refresh is idempotent. Repeating it with unchanged evidence does not manufacture revisions or events.

## Pending confirmation proposal

`black_crown_begin_ownership_confirmation(...)` creates only a pending proposal.

Required controls:

- review switch enabled;
- valid case ID;
- exact expected revision;
- case row locked with `SELECT ... FOR UPDATE`;
- proposed account already exists and is active/provisional;
- confirmation method allowlisted;
- actor reference is a SHA-256 hash;
- reason is a stable machine code;
- blocked cases require `support_dual_confirmation` and an existing candidate account.

The RPC updates only the review case and inserts one audit event. It does not touch accounts, identities, product rows or entitlements.

Supported proposal methods:

- `telegram_challenge`;
- `website_session`;
- `support_dual_confirmation`.

A proposal is not proof and grants no authority.

## Cancellation contract

`black_crown_cancel_ownership_confirmation(...)` requires:

- review switch enabled;
- exact expected revision;
- pending case state;
- valid hashed actor reference;
- stable reason code.

It clears only the pending proposal and returns the case to:

- `blocked` when conflict/merge-pending source evidence remains;
- otherwise `open`.

Both proposal and cancellation reject null or stale revisions. This prevents an operator or concurrent process from modifying a case reviewed against older evidence.

## Transactional GAME validation

Migration 011 was executed against GAME inside `BEGIN ... ROLLBACK` before opening the PR.

The behavioral dry-run covered:

- initial case refresh;
- repeated idempotent refresh;
- proposal rejected while `ownership_resolution_review=false`;
- service-role enable;
- valid pending proposal;
- null revision rejection;
- stale revision rejection;
- valid cancellation;
- service-role disable;
- final refresh;
- privacy-safe queue output;
- browser grant audit;
- forbidden apply/confirm RPC audit;
- before/after product, account, identity and entitlement counts.

No SQL/tool error occurred.

The dry-run proved:

- queue cases were built from hashed migration evidence;
- no raw subject columns existed;
- browser table/view grants were zero;
- browser EXECUTE grants were zero;
- no ownership-apply/confirm/resolve function existed;
- proposal and cancellation events claimed zero owner, identity and entitlement writes;
- product owner counts remained unchanged;
- account, identity and entitlement counts remained unchanged;
- the switch ended disabled.

The transaction was rolled back. A separate rollback audit proved:

- review tables absent;
- review view absent;
- review functions absent;
- review flag absent;
- migration history entry absent;
- all source row counts unchanged.

Migration 011 remains unapplied until its PR is merged, exact Render production is verified, and the GAME pre-apply baseline is rechecked.

## Production rollout

Safe sequence:

1. merge migration and contract tests with the review switch staged disabled;
2. verify exact Render SHA and protected production contracts;
3. capture GAME pre-apply counts and existing migration state;
4. apply migration 011 once;
5. verify review flag remains false;
6. verify queue cases and hashed-subject privacy;
7. run refresh a second time and prove idempotency;
8. verify no proposal/event exists;
9. verify no owner, identity or entitlement count changed;
10. run Supabase security/performance advisors;
11. keep the review workflow disabled until a separate authenticated confirmation client exists.

## Future boundary

A later phase may implement verified Telegram and Website confirmation challenges. That must be a separate PR and must still avoid automatic merge.

Any future function that applies canonical ownership requires all of the following before it can exist:

- explicit user confirmation from the affected identity providers;
- exact case revision;
- conflict-aware two-party confirmation where applicable;
- entitlement-preservation proof;
- immutable audit evidence;
- rollback and recovery contract;
- behavioral tests proving no unrelated Player Brain or history movement;
- a separate controlled production gate.
