# BLACK CROWN OPS v26 — Causal Operator Context

## Objective

Make Operator Twin intelligence part of the single shared Intelligence Core used by Telegram text, accepted Telegram voice transcripts and the Mini App.

v25 created the server-authoritative Operator Twin and mission lifecycle. v26 closes the reasoning loop: ordinary tactical answers now receive a bounded, truth-calibrated operator context instead of raw derived analytics.

## Context contract

`OperatorContextProjector` emits `bco_operator_context_v26` with:

- qualitative readiness / risk / confidence / momentum;
- calibrated claims with evidence count, source diversity, recency, trend and uncertainty;
- bounded evidence provenance without internal weights;
- explicit unknown dimensions;
- current mission and success condition;
- session phase and last review.

It does **not** expose internal evidence weights, priority calculations or hidden scoring mechanics.

## Truth semantics

- verified fact: scoped observed/reported fact;
- high-confidence player pattern: strong recurring pattern, not certainty;
- weak pattern: tentative;
- hypothesis: measurement target, not diagnosis;
- unknown: must remain unknown.

One result does not prove causation. Emotion detection changes delivery only and never becomes evidence of a persistent tilt trait.

## Shared brain integration

`ConversationService` injects Operator Context only after a trusted server-side Telegram identity is resolved. Untrusted/demo Mini App requests never receive persistent operator context.

The same `ConversationService -> BrainEngine -> AIHook -> PromptBuilder` path is shared by:

- Telegram text;
- high-confidence/confirmed voice transcripts;
- Mini App live/non-live AI requests.

No second conversational model is introduced.

## Prompt safety

When Operator Context is present, raw `derived_intelligence` is quarantined from the generic profile block so it cannot bypass the calibrated truth model.

If a mission is active, relevant coaching should align to it instead of silently replacing the player's current objective.

## Rollback

`OPERATOR_CONTEXT_BRIDGE_ENABLED=0`

This disables only the v26 context bridge. v25 Operator Twin / Mission Control, v18 Live Intelligence, Duplex Voice, VOD, Premium authority and persistent memory remain available.

## Release

- `APP_VERSION=26.0.0`
- `RELEASE_CONTRACT=bco-causal-operator-context-v26`
