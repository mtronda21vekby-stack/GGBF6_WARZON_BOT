# Canonical identity

Supabase project: `GAME` (`wqriwhciqvrbhkkiuhxb`).

```text
website_auth ─┐
telegram ─────┼─> black_crown_identities ─> black_crown_user_id
apple/iOS ────┘                                │
                                              ├─> bco_players
                                              ├─> bco_messages
                                              └─> blackcrown_entitlements
```

Platform identities are authentication mechanisms. `black_crown_user_id` is the product identity.

For native requests the server validates the Supabase Auth JWT and uses the Auth user UUID as the `apple` provider subject. It never auto-merges by email and never accepts a canonical UUID from the request. A new Apple identity without a verified account link fails closed with `canonical_link_required`; linking stays within the existing website/Telegram proof and merge system.

No new iOS account, player, message or memory table is introduced. RLS and server-only access for product tables are unchanged.

## Verified Apple link

An unlinked Apple-authenticated iPhone starts a short-lived Telegram challenge through the native API. The API derives the Apple subject from the validated Supabase JWT and never accepts a canonical account ID. Only the existing bot can complete the challenge, using the Telegram sender observed in a private chat.

The database completion function locks the challenge and Apple identity, requires an active Telegram identity and an active Website identity on the same active canonical account, enforces the existing unique `(provider, provider_subject)` constraint, writes `apple_identity_linked` to `black_crown_identity_events`, and consumes the challenge in one transaction. Codes are 192-bit URL-safe random values and only their SHA-256 hashes are stored. Challenges expire after at most 15 minutes and are single-use/replay-aware.

`black_crown_apple_link_challenges` and its four RPCs are service-role-only with RLS enabled. iOS receives only link metadata and a one-time Telegram URL; it never receives service credentials or a selectable owner ID.
