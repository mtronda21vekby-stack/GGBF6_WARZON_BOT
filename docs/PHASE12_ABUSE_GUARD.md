# BLACK CROWN OPS — Phase 12 Abuse Guard / Cost Control

## Mission

Protect expensive BLACK CROWN capabilities from burst spam, duplicate Telegram delivery, and forged-ID churn without making normal navigation brittle or moving billing logic into the intelligence core.

## Protected boundaries

Rate limiting is applied where cost is actually incurred:

- AI generation through the canonical `ConversationService` boundary;
- VOD media analysis before Telegram download/frame extraction/vision;
- Piper TTS synthesis before audio generation.

Opening menus, changing settings, viewing the Command Center, and rejecting oversized media do not consume these capability budgets.

## Per-player and global budgets

Each expensive category has both per-player and process-global rolling windows.

Defaults:

- AI: 12/min and 120/hour per player; 180/min and 1800/hour global;
- VOD: 3/10 min and 12/hour per player; 30/10 min and 120/hour global;
- Voice: 10/min and 60/hour per player; 120/min and 1200/hour global.

All limits are configurable through environment variables. Values `<= 0` disable the corresponding window.

Global buckets are explicitly protected from bounded-cache eviction. An attacker cannot reset the global budget by cycling through forged chat IDs.

## Telegram replay protection

`update_id` values are remembered in a bounded TTL cache. A repeated Telegram update receives HTTP 200 with `duplicate=true` and is skipped before AI/VOD/TTS work.

Default replay TTL: 15 minutes.

This is operational idempotency, not persistent user memory.

## Webhook payload cap

Telegram webhook payloads are capped at 256 KiB by default. The limit is checked against both `Content-Length` (when present) and the actual body length before JSON parsing.

Oversized updates return HTTP 413.

## Failure semantics

Usage guard internals fail open so a programming error in the guard cannot take the bot offline. Actual limit decisions fail closed for the expensive capability and return a short cooldown message.

Telegram duplicate delivery always receives HTTP 200 so Telegram does not enter an unnecessary retry loop.

## Privacy

Readiness telemetry exposes only aggregate counters:

- allowed/blocked counts by capability;
- active bucket count;
- configured windows;
- number of duplicate Telegram updates.

It does not expose chat IDs, prompts, responses, tokens, Supabase keys, or Telegram payload content.

## Persistence and scale

The guard is intentionally process-local for the current single Render service. It resets on deploy/restart. If BLACK CROWN moves to multiple workers, this boundary should be backed by a shared atomic limiter (for example Redis) without changing the calling contracts.

## Billing / entitlements

Phase 12 does **not** invent a Premium entitlement or payment state. Billing authorization remains a separate server-authoritative phase once a real payment/provider source of truth is selected.

## Release gate

Phase 12 publishes:

- `APP_VERSION=12.0.0`
- `RELEASE_CONTRACT=bco-aaa-v12`

Production CI accepts the release only when:

- exact version is live on Render;
- Supabase persistent storage startup probe is healthy;
- abuse guard is enabled;
- Telegram replay dedupe is enabled.
