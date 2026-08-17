# BLACK CROWN OPS v25 — Operator Twin / Adaptive Mission Intelligence

## Goal

Turn persistent Player Intelligence into an evidence-calibrated operator model and measurable mission loop without inventing RPG-style skill percentages.

## Truth model

Operator claims are classified as:

- `verified_fact` — explicit bounded report/metric or persisted mission result;
- `high_confidence_player_pattern` — repeated evidence across multiple source types;
- `weak_pattern` — repeated or cross-source signal that is not yet strong enough;
- `hypothesis` — single-source/sparse signal;
- `unknown` — insufficient evidence.

Unknown remains unknown. The UI does not synthesize hidden 0–100 skill scores for derived dimensions.

## Operator dimensions

- aim
- movement
- positioning
- rotations
- decision making
- aggression
- survivability
- comms
- discipline
- consistency
- tilt susceptibility

Each dimension exposes confidence, evidence count, source diversity, recency, trend and uncertainty.

## Adaptive mission lifecycle

`PRE_SESSION -> LIVE_OBJECTIVE -> POST_SESSION_REVIEW -> MEMORY_UPDATE -> NEXT_MISSION`

Mission state is persisted through the existing progression/training/episode store. No database migration is required. Mission IDs are deterministic optimistic-concurrency tokens; stale actions fail closed.

When evidence is insufficient, the system generates an `OPERATOR BASELINE CAPTURE` calibration mission instead of pretending to know the player's weakness.

## Surfaces

Telegram Command Console:

- existing OPERATOR entry now opens the evidence dossier;
- current mission can be accepted in-place;
- active mission can be reported CLEAN / MIXED / FAILED;
- same-message editing remains authoritative;
- private Telegram identity boundary remains unchanged.

Mini App:

- dedicated Operator tab;
- evidence matrix without score bars;
- readiness/risk/confidence/momentum as calibrated states;
- mission accept and post-session result controls;
- server-authoritative Telegram initData boundary.

## Rollback

- `OPERATOR_INTELLIGENCE_ENABLED=0`
- `ADAPTIVE_MISSION_CONTROL_ENABLED=0`

Existing v18 Live Intelligence, v24.1 Duplex Voice, Premium authority, VOD and persistence remain independent.

## Release

- `APP_VERSION=25.0.0`
- `RELEASE_CONTRACT=bco-operator-twin-missions-v25`
