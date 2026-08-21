# BLACK CROWN Canonical Ownership Dual-Write v1

## Status

Phase 2B enables an additive canonical-owner projection on future writes. It does **not** switch the production read path away from legacy keys.

- Audited base `main`: `c319f8832bdb18907fdae095ab505ec9ae23073a`.
- Product release remains `44.0.0`; no release bump is part of this phase.
- Website, Telegram Bot and Mini App presentation are unchanged.
- GAME is the only Supabase project in scope.
- Legacy `chat_id`, `telegram_user_id` and `site_user_id` values remain mandatory and continue to support rollback.

## Authority model

The browser, Telegram payload, Mini App profile and caller-supplied JSON have no authority over `black_crown_user_id`.

For every covered INSERT or UPDATE, a server-owned trigger:

1. reads the legacy provider subject already required by the table;
2. resolves eligible identities from `black_crown_identities` joined to `black_crown_accounts`;
3. accepts only `active` or `provisional` identities belonging to an `active` or `provisional` account;
4. replaces any caller-supplied canonical owner with the server result;
5. preserves an existing non-null owner instead of silently transferring it;
6. records `unresolved`, `conflict` or `merge_pending` evidence without storing the raw provider subject.

`provisional` Telegram identities are eligible because the current server resolver creates a provisional canonical account before a new private-chat user writes profile, memory or analytics state. The dual-write trigger never creates identities itself.

## Covered write surfaces

| Surface | Legacy subject retained | Canonical source | Conflict behavior |
|---|---|---|---|
| Player profile, summary and derived intelligence | `chat_id` | Telegram identity | existing owner preserved; conflict recorded |
| Conversation messages | `chat_id` | Telegram identity | existing owner preserved; conflict recorded |
| Episodes | `chat_id` | Telegram identity | existing owner preserved; conflict recorded |
| Recurring mistakes and idempotency receipts | `chat_id` | Telegram identity | existing owner preserved; conflict recorded |
| Progression and training | `chat_id` | Telegram identity | existing owner preserved; conflict recorded |
| Activity analytics | `telegram_user_id` | Telegram identity | existing owner preserved; conflict recorded |
| Entitlements | `site_user_id` | Website identity | Telegram/client values cannot transfer Premium |
| Account link | Website + Telegram subjects | both identities must exist and agree | disagreement becomes `merge_pending` |
| Account-link event | one verified identity, or both agreeing | Website and/or Telegram identity | disagreement becomes `merge_pending` |

Eleven `BEFORE INSERT OR UPDATE` triggers enforce this boundary at the canonical expensive persistence layer, including legacy RPCs and direct service-role writes.

## Operational rollback

`black_crown_ownership_runtime_flags` is server-only and contains the `canonical_dual_write` switch.

The service-role-only function:

```sql
select public.black_crown_set_ownership_runtime_flag(
  'canonical_dual_write',
  false,
  'incident reference and operator reason'
);
```

provides immediate non-destructive rollback:

- new INSERTs continue through the legacy write path with a null canonical projection;
- UPDATEs retain their previous canonical owner;
- no canonical column, identity, Player Brain row, message or entitlement is deleted;
- already projected ownership and audit evidence remain available for diagnosis;
- re-enabling the flag resumes server-resolved dual-write.

Browser roles cannot read or mutate the flag table or call the flag function.

## Conflict and privacy contract

A caller can never overwrite a different existing owner. The runtime instead:

- keeps the existing owner;
- normalizes the candidate account list;
- writes a privacy-safe migration-state entry using a SHA-256 subject hash;
- emits one idempotent conflict event identified by a conflict fingerprint;
- sets `silent_merge_allowed=false`;
- sets `entitlement_transfer_allowed=false` for linked-identity conflicts.

If Website and Telegram resolve to different accounts, both accounts remain intact and the state is `merge_pending`. Manual controlled resolution remains a later phase.

## GAME baseline before Phase 2B

Fresh read-only capture before implementation:

- ownership mappings: 3 resolved, 2 unresolved, 0 conflict, 0 merge-pending;
- identity conflicts: 0;
- messages: 172/172 projected;
- episodes: 5/5 projected;
- progression: 3/3 projected;
- training: 1/1 projected;
- account link and link event: fully projected;
- profiles: 1/2 projected;
- activity rows: 1/2 projected.

The two unresolved projections belong to one legacy subject with no canonical identity. Phase 2B deliberately leaves that subject legacy-only until a real server identity is resolved; it does not manufacture or merge an account from historical data.

## Transactional GAME validation

The full migration and behavioral suite were executed against GAME inside `BEGIN ... ROLLBACK` on 2026-08-21 UTC.

The transaction proved:

- all DDL, functions, RLS, policies, grants, view and 11 triggers install successfully;
- a forged caller-supplied owner is replaced by the server-resolved account;
- a provisional Telegram identity receives the correct canonical projection;
- disabling the rollback flag prevents canonical assignment on new INSERTs;
- re-enabling resumes projection without changing legacy data;
- a changed identity mapping cannot transfer an existing owner;
- owner mismatch produces `conflict` state and an idempotent audit event;
- agreeing Website and Telegram identities resolve one account link;
- disagreeing linked identities leave the owner null and produce `merge_pending`;
- a one-sided verified account-link event resolves safely;
- an entitlement uses Website identity authority, not the supplied canonical ID;
- `ROLLBACK` leaves no runtime flag table, status view, function or trigger residue.

The initial behavioral attempt also rolled back cleanly after the test fixture used an event type rejected by the existing GAME constraint. The fixture was corrected to the existing allowed `linked` value; production schema behavior was not changed to accommodate the test.

## Runtime status

`black_crown_ownership_runtime_status` is service-role-only and reports:

- schema version `bco-canonical-owner-v2`;
- dual-write flag state, reason and timestamp;
- installed and expected trigger counts;
- per-table canonical coverage;
- ownership migration-state totals.

This evidence is intended for release verification and later `/health/details` integration. It is not exposed to the browser.

## Rollout sequence

1. Merge this migration after Required Gate, Intelligence CI, Compatibility Contracts and CodeQL are green.
2. Re-check that `main` has not moved or reconcile deliberately.
3. Apply the exact merged migration to GAME.
4. Verify 11 triggers, browser-denied grants, flag state, unchanged row counts and zero new conflicts.
5. Exercise a transactional future-write smoke test and roll it back.
6. Verify Render deploys the exact merge SHA even though this phase does not alter HTTP behavior.
7. Keep legacy reads authoritative during the observation window.
8. Begin canonical-first dual-read only in a separate Phase 2C PR after coverage and parity evidence are sufficient.
