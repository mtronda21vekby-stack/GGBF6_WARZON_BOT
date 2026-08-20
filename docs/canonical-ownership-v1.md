# BLACK CROWN Canonical Product Ownership v1

## Status

Phase 2A establishes an additive canonical-owner projection. It does **not** switch the runtime away from legacy keys yet.

- Product-state runtime authority before Phase 2B: legacy `chat_id` / `telegram_user_id` / `site_user_id`.
- Canonical account authority: server-resolved `black_crown_user_id` from `black_crown_identities`.
- Browser authority over `black_crown_user_id`: none.
- Automatic account merge: prohibited.
- Automatic Premium transfer during an identity conflict: prohibited.

## Fresh GAME baseline

Captured from Supabase GAME at `2026-08-20T05:19:37.023754+00:00` before applying the migration:

| Surface | Rows |
|---|---:|
| `bco_players` | 2 |
| `bco_messages` | 172 |
| `bco_episodes` | 5 |
| `bco_player_mistakes` | 0 |
| `bco_mistake_receipts` | 0 |
| `bco_progression_events` | 3 |
| `bco_training_sessions` | 1 |
| `bco_user_activity` | 2 |
| `blackcrown_account_links` | 1 |
| `blackcrown_account_link_events` | 1 |
| `blackcrown_entitlements` | 0 |
| `black_crown_accounts` | 1 |
| `black_crown_identities` | 2 |

Identity providers: one active Telegram identity and one active Website identity. The one active legacy account link resolved to the same canonical account on both sides; no Website/Telegram canonical conflict was present at capture time.

These counts are diagnostic evidence, not a release constant. Production can continue writing while migration work is reviewed.

## Ownership matrix

| Domain | Legacy lookup retained | Canonical projection source | Conflict behavior |
|---|---|---|---|
| Profile / Player Brain | `chat_id` | active Telegram identity | unresolved owner stays null |
| Messages / episodes | `chat_id` | active Telegram identity | unresolved owner stays null |
| Mistakes / receipts | `chat_id` | active Telegram identity | unresolved owner stays null |
| Progression / training | `chat_id` | active Telegram identity | unresolved owner stays null |
| Analytics activity | `telegram_user_id` | active Telegram identity | unresolved owner stays null |
| Entitlements | `site_user_id` | active Website identity | no Telegram-driven transfer |
| Account links | Website + Telegram legacy subjects | both active identities must agree | `merge_pending`; owner remains null |
| Link audit events | whichever verified subject is present | one verified identity, or both agreeing | conflict remains null |

## Migration states

`black_crown_ownership_migration_state` stores only a SHA-256 subject hash, never the raw legacy subject.

- `resolved`: exactly one server-owned canonical candidate exists.
- `unresolved`: no authoritative mapping exists yet.
- `conflict`: more than one active candidate exists for one provider subject.
- `merge_pending`: Website and Telegram resolve to different canonical accounts.

For `merge_pending`:

1. both canonical accounts are preserved;
2. `black_crown_user_id` on the legacy link remains null;
3. an idempotent `black_crown_identity_events` audit event is emitted;
4. Premium transfer is explicitly disabled;
5. manual controlled resolution is required in a later contract.

## Backfill contract

`black_crown_backfill_product_ownership(batch_size)` is server-only, bounded to `1..50000`, resumable and idempotent for product rows:

- it only considers rows where `black_crown_user_id is null`;
- it never overwrites a non-null owner;
- it never creates an account or identity;
- it never deletes or rewrites a legacy key;
- account links are projected only when Website and Telegram identities agree;
- every run records updated-row counts, mapping states and per-table coverage.

A bounded initial pass is part of the migration. Re-running the function processes only remaining null projections.

## Transactional validation evidence

The complete migration was executed against GAME inside `BEGIN ... ROLLBACK` before opening the PR. The dry-run completed successfully, including DDL, FK validation, RLS, backfill, mapping-state refresh, audit-event logic and coverage calculation.

Dry-run result at that moment:

- mapping states: 3 resolved, 2 unresolved, 0 conflict, 0 merge-pending;
- full canonical coverage for messages, episodes, progression, training, account link and link event;
- 50% projected coverage for profiles and analytics because one legacy subject had no active canonical identity;
- no mutation remained after rollback.

Post-rollback audit confirmed:

- foundation tables: absent;
- foundation functions: absent;
- coverage view: absent;
- new owner columns: absent;
- `bco_user_activity` RLS: restored to its original disabled state.

## Rollout sequence

1. **Phase 2A — this migration:** additive columns, audit ledger, conflict state, backfill and metrics.
2. **Phase 2B:** server-resolved dual-write; legacy write remains mandatory.
3. **Phase 2C:** canonical-first dual-read with measured fallback to legacy rows.
4. **Phase 2D:** conflict-resolution workflow and controlled account confirmation.
5. **Phase 2E:** only after coverage and parity gates, make canonical ownership authoritative.

## Rollback

The safe rollback is operational, not destructive:

- disable canonical dual-write/read flags;
- continue legacy reads and writes;
- preserve additive owner columns and audit records for diagnosis;
- revert the runtime PR that enabled canonical behavior.

Dropping canonical columns during an incident is prohibited because it can destroy migration evidence and already-projected ownership.
