# BLACK CROWN OPS — Phase 6 Premium Command Center

## Mission

Turn the Mini App from a collection of controls into a server-authoritative player intelligence dashboard backed by the same profile/memory used by Telegram coaching.

## Trust model

`/webapp/api/intelligence` requires valid Telegram Mini App `initData`.

The API never accepts a client-supplied player identity or profile. It resolves the Telegram identity server-side and reads:

- ProfileService
- persistent Storage
- recurring mistakes
- training sessions
- progression events
- VOD sampled-frame episodes
- derived intelligence/trends

If Telegram verification fails, private player intelligence is not returned.

## Dashboard

The Command Center is loaded as an additive Mini App module through `bco.engine.js`; the large existing `index.html` and `app.js` bootstrap are not rewritten.

The new `Intel` tab contains:

- data coverage;
- recurring mistake count;
- training/progression activity;
- player game/input/rank/KD/goal/focus/voice state;
- evidence-only skill matrix;
- match/progression sparkline;
- derived trends;
- recurring mistake frequency;
- training history;
- recent sampled-frame VOD intelligence.

## No fake scoring

`aim_score`, `movement_score`, `positioning_score`, `decision_score`, and `comms_score` are displayed only when the persistent profile contains evidence-backed values. Unknown values remain `—`.

The dashboard does not convert branding, message count, or model opinion into a fake skill score.

## Data coverage

Coverage is a readiness indicator, not a player rating. It increases when BLACK CROWN has more useful evidence such as:

- known player profile fields;
- evidence-backed skill values;
- recurring mistake observations;
- progression reports.

## Progress charts

The dashboard prefers, in order:

1. accuracy percentage;
2. kills;
3. placement;
4. score;
5. Zombies wave.

A chart appears only after at least two observed values exist.

## VOD

The dashboard shows only persisted VOD analysis metadata and summaries. Raw video or extracted frames are never returned or stored in Supabase.

## Architecture

```text
Telegram Mini App
    ↓ signed initData
POST/GET /webapp/api/intelligence
    ↓ verify_init_data
CommandCenterService
    ↓
ProfileService + Storage
    ↓
Supabase GAME (when configured)
```

The UI remains useful with in-memory fallback, but durable history requires the existing Supabase persistence configuration.

## Security

- no service-role key in JavaScript;
- no direct browser access to `bco_*` tables;
- no client-selected chat/user id;
- response uses `Cache-Control: no-store`;
- server-side profile is authoritative;
- private dashboard fails closed outside verified Telegram context.
