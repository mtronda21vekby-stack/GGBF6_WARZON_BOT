# BLACK CROWN OPS v19 — Adaptive Mission Control

## Objective

Turn persistent Player Intelligence into one active, evidence-backed mission that the player can accept, execute, report and measure.

The v19 system does not generate decorative daily quests. It selects a single limiting factor from trusted player evidence, builds a bounded protocol and records the outcome through the established server-authoritative storage boundary.

## Mission selection

Mission Control evaluates:

- recurring mistakes and their frequency/recency;
- explicit weaknesses and training focus;
- evidence-backed skill scores;
- recent metric trends;
- previous mission outcomes and focus repetition;
- current game, input, role and reasoning mode.

The selected focus is one of:

- aim;
- movement;
- positioning;
- decision-making;
- communications.

When evidence is sparse, Mission Control issues a calibration mission rather than pretending to know the player's main weakness.

## Mission contract

Each mission contains:

- deterministic mission ID;
- evidence and selection rationale;
- objective;
- three execution phases;
- one in-match rule;
- one measurable success condition;
- estimated duration;
- readiness, momentum and risk telemetry.

Only one mission may be active at a time.

## Lifecycle

```text
candidate → accepted → completed
```

Acceptance and completion are idempotent. A stale or foreign mission ID is rejected as a conflict rather than mutating the current player state.

Completion records:

- clean / mixed / failed outcome;
- bounded reported metrics;
- operator note;
- mission score;
- progression and training events;
- the evidence required to generate the next adaptive mission.

## Telegram Command Console

The native console exposes a Mission Control module with:

- current mission status;
- objective and evidence;
- protocol phases;
- accept action;
- clean / mixed / failed completion actions;
- refresh and navigation inside the existing single-message console.

All actions require a private verified Telegram identity.

## Mini App

The Premium Command Center contains a dedicated mission surface with:

- active/candidate mission card;
- readiness / momentum / risk indicators;
- evidence rail;
- phase timeline;
- accept and completion controls;
- result note and optional bounded match metrics;
- automatic refresh of Player Intelligence after completion.

The API uses verified Telegram Mini App `initData`; client-supplied identity cannot select or mutate another player's mission.

## Security and persistence

- server-side identity is authoritative;
- no mission mutation is allowed in demo/untrusted context;
- mission IDs prevent stale-client writes;
- partial AI output is not involved in mission persistence;
- generic progression/training storage is reused, so no fragile request-time migration is required;
- metrics are allow-listed and bounded;
- mission notes are length-limited;
- existing abuse, replay and persistence recovery controls remain active.

## Runtime rollback

```text
ADAPTIVE_MISSION_CONTROL_ENABLED=0
```

Disabling the flag removes mission generation and mutation while leaving v18 Live Intelligence, player memory, VOD, voice and Premium authority intact.

## Release target

```text
19.0.0 / bco-adaptive-mission-control-v19
```
