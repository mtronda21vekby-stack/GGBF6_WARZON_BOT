# BLACK CROWN OPS — Phase 3 Live Game Intelligence

## Goal

Give current/patch questions a first-party evidence layer without turning web scraping or model memory into false certainty.

Phase 3A uses **curated official-source snapshots**. It deliberately does not scrape publisher pages on every Telegram request.

## Runtime flow

```text
Current/meta question
  -> Intent Router
  -> OfficialSnapshotProvider
  -> official-domain validation
  -> verified_at + TTL freshness check
  -> VERIFIED_CURRENT or DATED_SOURCE
  -> existing currentness gate
  -> PromptBuilder / AI
```

Non-current tactical questions continue to use the existing static repository knowledge layer.

## Official source snapshots

Stored under:

```text
app/content/live/warzone.json
app/content/live/bo7.json
app/content/live/bf6.json
```

Initial snapshot verification date: **2026-08-16 UTC**.

Sources:

- Warzone — Raven Software / Call of Duty Season 05 patch notes
- Black Ops 7 — Treyarch / Call of Duty Season 05 patch notes
- Battlefield 6 — official Battlefield / EA Update 1.4.1.0 notes

Every snapshot contains:

- game
- title
- publisher
- source kind
- first-party URL
- published timestamp
- explicit verification timestamp
- short factual summaries/tags

The data is paraphrased rather than copying patch-note pages wholesale.

## Freshness contract

Environment variable:

```text
LIVE_KNOWLEDGE_MAX_AGE_HOURS=168
```

Default: 168 hours (7 days).

A snapshot becomes `VERIFIED_CURRENT` only when all conditions are true:

1. source URL belongs to an approved first-party domain;
2. `verified_at` parses correctly;
3. `verified_at` is not in the future;
4. snapshot age is within the configured TTL.

After TTL expiry the same snapshot automatically degrades to `DATED_SOURCE`.

The v1 factuality gate then refuses to silently answer a request that requires current data.

This means a forgotten snapshot fails **closed**, not open.

## Meta policy

Official patch notes can verify buffs, nerfs, maps, modes and developer balance statements.

They generally do **not** constitute a definitive competitive weapon ranking.

For `META_CURRENT`, the provider injects an explicit scope rule:

- patch changes may support a patch-informed recommendation;
- a recommendation/inference must not be presented as an official verified meta ranking;
- exact current attachments must not be invented if they are absent from trusted data.

## Game selection

For current questions, an explicit game name in the user's text overrides the stored profile game. Example:

```text
Profile: Warzone
Question: "Что изменили в последнем патче BO7?"
```

The provider selects the BO7 snapshot.

## Current initial coverage

### Warzone

Snapshot includes selected Season 05 weapon-balance facts and current map/content context from Raven Software.

### Black Ops 7

Snapshot includes selected Season 05 multiplayer/ranked balance and Zombies changes from Treyarch.

### Battlefield 6

Snapshot includes the official Update 1.4.1.0 / Season 4 Pacific Front state selected during verification.

## Updating snapshots

Do **not** extend `verified_at` merely because the URL still returns HTTP 200.

To refresh a snapshot:

1. open/search the first-party source;
2. verify that the factual summaries still match the current official page/state;
3. update facts if needed;
4. update `published_at` when source release changed;
5. set `verified_at` to the actual verification time;
6. run tests/CI.

A future Phase 3B can automate discovery where a stable official feed/API exists, but it must preserve provenance and fail-closed freshness semantics.

## Security / reliability

- No API key is required for official snapshots.
- No third-party SEO/meta site is trusted as `VERIFIED_CURRENT`.
- No runtime arbitrary-URL fetching is performed.
- Approved source hosts are allowlisted in code.
- Existing Telegram, Mini App, player memory and storage paths are unchanged.

## Supabase note

Phase 2 persistent-storage code remains stacked below this branch. The connected Supabase project was identified, but applying its migration through the current connector is still blocked by the connector's server-side write scope. Phase 3 does not depend on that migration and therefore remains independently testable.
