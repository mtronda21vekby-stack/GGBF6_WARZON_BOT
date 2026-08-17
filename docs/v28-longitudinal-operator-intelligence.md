# BLACK CROWN OPS v28 — Longitudinal Operator Intelligence

Release: `28.0.0 / bco-longitudinal-operator-intelligence-v28`

## Contract

- A directional player trend requires at least 3 explicit completed mission outcomes.
- One match never proves improvement or regression.
- Sampled-frame VOD evidence may corroborate or contradict an explicit mission outcome, but it never rewrites that outcome.
- Contradictions are retained and reduce interpretation confidence.
- Longitudinal output is an association signal, not a causal claim.
- No hidden RPG-style player score is introduced.

## Window

The runtime uses up to 12 recent completed mission cycles and exposes at most 6 bounded cycle summaries to the Operator Twin snapshot.

## Rollback

`OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED=0`

This removes only the v28 longitudinal overlay. v27 Operator Twin, Adaptive Missions, shared Operator Context and VOD Mission Evidence Fusion remain available.

## Production readiness

The production gate requires:

- `context_schema=bco_operator_context_v28`
- `longitudinal_schema=bco_longitudinal_operator_v28`
- `longitudinal_minimum_cycles=3`
- contradiction detection enabled
- `association_not_causation`
- `longitudinal_causal_claims=false`
- all v18-v27 readiness contracts preserved
