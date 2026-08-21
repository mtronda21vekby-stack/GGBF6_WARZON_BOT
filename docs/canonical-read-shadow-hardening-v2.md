# BLACK CROWN Canonical Read Shadow Hardening v2

## Scope

This phase hardens the comparison-only canonical read shadow introduced by PR #74. It does **not** switch product read authority.

- Base `main`: `8b8cc80948c17d6bcd7525aae657b92902d8ad69`.
- Product release remains `44.0.0`.
- GAME is the only Supabase project in scope.
- `canonical_dual_write` and `canonical_shadow_read` remain independent controls.
- Every product caller still receives the established legacy `chat_id`-scoped value.
- No Website, Telegram Bot, Mini App or Voice presentation is changed.

## Hardening changes

### No resolved-owner cache

A successful canonical owner UUID is resolved again for every sampled shadow read. It is never retained across reads.

Only unresolved, conflicting or failed identity lookups use a short bounded negative cache. A successful `resolve_telegram_identity` call invalidates that negative cache immediately.

This removes the window where a controlled account relink could leave shadow comparison reading a previous canonical owner. Shadow values were never returned to callers, but stale comparison evidence is still unacceptable.

### Sanitized database control

The application now reads `black_crown_canonical_read_runtime_status` instead of reading the free-form runtime flag reason directly.

The readiness surface exposes only stable machine states:

- `local_shadow_disabled`;
- `database_disabled`;
- `database_enabled`;
- `dual_write_disabled`;
- `mapping_conflict`;
- `schema_mismatch`;
- `control_lookup_failed`.

It never publishes the operator-entered database reason, provider subject, canonical UUID, profile content, history content or credentials.

### Fail-closed shadow execution

Canonical comparison is skipped and one legacy read is returned when:

- runtime status schema is not `bco-canonical-read-shadow-v2`;
- dual-write is disabled;
- any canonical identity conflict exists;
- any account link is `merge_pending`;
- the control view cannot be read;
- the local shadow switch is disabled;
- the database shadow switch is disabled.

Coverage incompleteness does not stop evidence collection. It instead blocks promotion readiness. This lets the shadow measure parity while explicitly preventing canonical-first promotion.

## Promotion evidence

Migration 010 appends privacy-safe aggregate evidence to the existing status view while preserving the original v1 column names, types and order.

New columns:

- `coverage`;
- `shadow_surface_coverage_ready`;
- `promotion_ready`;
- `promotion_blockers`.

Covered shadow surfaces:

- `bco_players`;
- `bco_messages`;
- `bco_episodes`;
- `bco_player_mistakes`;
- `bco_training_sessions`;
- `bco_progression_events`.

Promotion requires:

- shadow enabled;
- dual-write enabled;
- zero identity conflicts;
- zero merge-pending mappings;
- complete canonical projection on every covered surface.

Known blocker codes:

- `shadow_disabled`;
- `dual_write_disabled`;
- `identity_conflict`;
- `merge_pending`;
- `coverage_incomplete`;
- `schema_mismatch`;
- `control_error`.

These codes are allowlisted before entering process telemetry.

## Transactional GAME validation

Migration 010 was executed against GAME inside `BEGIN ... ROLLBACK`.

The first dry-run identified two PostgreSQL compatibility requirements before PR creation:

1. `CREATE OR REPLACE VIEW` cannot rename existing columns;
2. it cannot change existing `integer` columns to `bigint`.

The migration was corrected to preserve the exact original nine columns and types, appending only the four new evidence columns.

The final transactional dry-run proved:

- schema version advanced transactionally to `bco-canonical-read-shadow-v2`;
- `canonical_shadow_read=true`;
- `canonical_dual_write=true`;
- resolved mappings: 3;
- unresolved mappings: 2;
- conflicts: 0;
- merge-pending: 0;
- `shadow_surface_coverage_ready=false`;
- `promotion_ready=false`;
- sole blocker: `coverage_incomplete`;
- browser grants on the status view: 0;
- existing column names, types and order remained compatible;
- new evidence columns were appended only;
- no raw subject or canonical UUID was returned as evidence.

Coverage observed in the dry-run:

| Surface | Canonical | Total | Coverage |
|---|---:|---:|---:|
| `bco_players` | 1 | 2 | 50% |
| `bco_messages` | 172 | 172 | 100% |
| `bco_episodes` | 5 | 5 | 100% |
| `bco_player_mistakes` | 0 | 0 | 100% |
| `bco_training_sessions` | 1 | 1 | 100% |
| `bco_progression_events` | 3 | 3 | 100% |

Product row counts remained unchanged, including 2 profiles, 172 messages, 5 episodes, 1 training session, 3 progression events and 2 activity rows.

The transaction was rolled back. Migration 010 is not applied before merge.

## Runtime and privacy contract

`/health/details` continues to report canonical shadow state through the existing quality telemetry path.

It reports:

- local and database enabled state;
- stable control state code;
- control check timestamp and exception class;
- promotion readiness and blockers;
- coverage readiness;
- aggregate identity conflict and merge-pending counts;
- comparison outcomes, latency and item counts;
- `read_authority=legacy`;
- `returns_legacy=true`;
- `canonical_returned_to_callers=false`;
- `canonical_primary_enabled=false`.

It does not expose the operator reason, account UUID, Telegram subject or product content.

## Rollback

Application rollback is a normal code revert. Database rollback remains non-destructive:

```sql
select public.black_crown_set_ownership_runtime_flag(
  'canonical_shadow_read',
  false,
  'incident reference'
);
```

Disabling shadow reads does not stop dual-write and does not delete canonical projections, legacy rows, Player Brain state, history, entitlements, accounts or audit evidence.

## Promotion boundary

`promotion_ready=false` is expected while `bco_players` contains one legitimate legacy-only historical row. This phase does not manufacture an identity, silently merge accounts or alter Premium to improve coverage.

Canonical-first reads remain prohibited until a later phase resolves legitimate legacy ownership, proves sustained parity and latency, defines canonical lifecycle operations, and passes a separate controlled promotion gate.
