# BLACK CROWN Canonical Lifecycle v1

## Status

Phase 2D introduces server-owned lifecycle semantics for conversation clear,
profile reset and explicit product-data purge. It does **not** promote canonical
reads and it does not automatically enable account-wide deletion.

- Schema: `bco-canonical-lifecycle-v1`
- Runtime flag: `canonical_lifecycle`
- Initial value: `false`
- Legacy read authority: unchanged
- Canonical read shadow: unchanged
- Product release: unchanged

## Authority

The application supplies only a trusted Telegram user ID. GAME resolves the
candidate account through active/provisional server-owned identities and active
or provisional BLACK CROWN accounts.

The browser and Mini App cannot submit:

- `black_crown_user_id`;
- lifecycle scope;
- conflict resolution;
- Premium state;
- an account merge decision.

Canonical lifecycle scope is allowed only when all three conditions hold:

1. the service-role runtime flag is enabled;
2. the Telegram provider subject resolves to exactly one eligible account;
3. the resolved owner is non-null.

Otherwise the operation uses the exact legacy Telegram subject. A conflict is
never widened into an account-wide deletion.

## Operations

### Clear conversation

`black_crown_clear_conversation(telegram_user_id)` deletes only messages.

- flag disabled/unresolved/conflict: exact `chat_id` rows;
- enabled and resolved: every message owned by the canonical account plus any
  remaining exact legacy-subject row.

### Reset profile

`black_crown_reset_player_profile(telegram_user_id)` preserves the historical
behavior of removing the player row, which includes profile, summary and
derived intelligence stored on that row.

- flag disabled/unresolved/conflict: exact `chat_id` row;
- enabled and resolved: every player row owned by the canonical account plus
  any remaining exact legacy-subject row.

### Purge product data

`black_crown_purge_product_data(telegram_user_id)` covers:

- messages;
- recurring mistakes and idempotency receipts;
- episodes / After Action evidence;
- training sessions;
- progression events;
- analytics activity;
- player profile, summary and derived intelligence.

It explicitly preserves:

- `black_crown_accounts`;
- `black_crown_identities`;
- Website/Telegram account links;
- entitlements and Premium authority.

Account unlink remains separate and does not delete Player Brain data.

## Deployment compatibility

The runtime calls the new lifecycle RPCs. During the narrow deployment window
before migration 010 is installed, only a confirmed PostgREST missing-function
response (`404` with `PGRST202`/`PGRST204`) can use the previous exact legacy
operation.

Authentication, authorization, transport and server failures never downgrade
to a direct legacy delete. They propagate to the existing resilient outbox.

## Privacy-safe readiness

`black_crown_lifecycle_runtime_status` contains only:

- schema and flag state;
- dual-write and shadow-read state;
- aggregate mapping counts;
- whether legacy fallback is available;
- explicit false values for account, identity and entitlement deletion.

It contains no owner UUID, Telegram subject, profile, history or secret.

## Rollback

The operational rollback is immediate and non-destructive:

```sql
select public.black_crown_set_ownership_runtime_flag(
  'canonical_lifecycle',
  false,
  'incident reference'
);
```

Rollback does not drop owner projections, audit evidence, accounts, identities
or existing product data. The exact legacy-subject behavior remains available.

## Promotion boundary

Canonical-first product reads remain prohibited until:

- shadow parity has sufficient measured volume;
- mismatch and ambiguity budgets pass;
- lifecycle behavior is deployed and verified;
- mapping conflicts remain zero;
- canonical coverage meets the explicit promotion threshold;
- rollback has been exercised.
