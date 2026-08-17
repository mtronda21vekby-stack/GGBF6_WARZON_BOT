# BLACK CROWN OPS v27 — Mission Evidence Fusion

## Objective

Close the measurement loop between real sampled-frame VOD analysis and the active Adaptive Mission without allowing vision evidence to become an automatic mission verdict.

v27 correlates high-confidence VOD findings to the **currently active mission** and persists them as bounded evidence. The player remains the authority for the final `CLEAN / MIXED / FAILED` post-session report.

## Evidence boundary

Source: `vision_sampled_frames`.

A correlated event may contain:

- mission id / focus;
- bounded sampled-frame signals;
- category and confidence;
- sampled frame count;
- VOD limitations;
- evidence classification.

It always carries:

`does_not_complete_mission = true`

It never creates an `operator_mission completed` event.

## Correlation rules

- only an accepted, not-yet-completed mission is eligible;
- only VOD findings at or above the confidence threshold are considered;
- findings must be relevant to the mission focus;
- visually weak domains such as comms or tilt are not inferred from a generic visual category;
- calibration missions can collect broad high-confidence visual evidence because their purpose is baseline capture;
- low-confidence or irrelevant findings become `insufficient_relevant_evidence`, not proof of success/failure.

## Operator Twin

An active mission snapshot may expose:

- evidence classification;
- evidence confidence;
- correlated clip count;
- bounded signal count;
- sampled-frame count;
- source / latest timestamp;
- sanitized evidence signals.

This evidence is propagated through `bco_operator_context_v27` to the shared Intelligence Core with an explicit no-auto-complete rule.

## Telegram / Mini App

Telegram VOD reports append a `MISSION EVIDENCE` section when a current mission exists. It explicitly says sampled-frame evidence is not the mission outcome.

The Operator dossier in Telegram and Mini App surfaces the correlated evidence while keeping the existing manual mission result controls.

## Persistence

No database migration is required. Existing progression and episode persistence is reused:

- `operator_mission_evidence` progression event;
- mirrored evidence episode;
- existing resilient Supabase outbox/replay path remains authoritative.

## Rollback

`MISSION_VOD_EVIDENCE_FUSION_ENABLED=0`

This disables only VOD-to-mission evidence correlation. VOD analysis, v25 Operator Twin/Mission Control, v26 shared Operator Context, voice, live intelligence and Premium authority remain intact.

## Release

- `APP_VERSION=27.0.0`
- `RELEASE_CONTRACT=bco-mission-evidence-fusion-v27`
