# BLACK CROWN OPS — Phase 13 Premium Account Link

Date: 2026-08-16
Release target: `13.0.0` / `bco-aaa-v13`

## Objective

Connect one Telegram identity to one BlackCrown website account through the shared Supabase `GAME` project while keeping Premium ownership fully server-authoritative.

## Telegram flow

- `💎 Premium` opens the authoritative status panel.
- `🔗 Связать с сайтом` creates a 192-bit URL-safe one-time token.
- The bot hashes the token with SHA-256 before calling Supabase.
- Supabase stores only the hash and invalidates the user's previous unused token.
- The button URL carries the token in a URL fragment, not a query string.
- The site requires its signed `bc_session` and asks for explicit confirmation.
- `🔓 Отвязать сайт` requires a second confirmation within 60 seconds.

Linking and unlinking are restricted to a private Telegram chat and use `message.from.id` as the identity authority.

## Premium rule

A link is not a purchase. The bot reports Premium as active only when the linked site account has a current server-owned entitlement:

```text
bco_premium
```

Local storage, KV ownership, mock checkout, usernames, button presses, and profile fields cannot create this entitlement.

## Failure behavior

The account bridge is isolated from the existing bot runtime:

- AI, VOD, voice, menus, memory, and Mini App continue working if the entitlement service is unavailable.
- Existing functionality is not hard-gated in Phase 13; the new authority launches in observe/status mode.
- `/health/details` reports only privacy-safe bridge readiness and never exposes a key or account identifier.

## Server authentication

The bot reuses the existing Render-only `SUPABASE_SERVICE_ROLE_KEY` for Supabase GAME.

- modern `sb_secret_*` keys are sent only as `apikey`;
- legacy service-role JWTs retain Bearer compatibility;
- publishable keys are rejected for all server entitlement RPCs.

No new secret is committed to GitHub.
