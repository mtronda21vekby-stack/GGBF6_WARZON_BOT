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

