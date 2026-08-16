# BLACK CROWN OPS — Phase 3 Live Game Intelligence

## Goal

Current/meta questions should use live official evidence instead of model memory or stale local JSON.

Phase 3 keeps the existing hard currentness gate: if the live official source cannot be verified, BLACK CROWN OPS refuses to present an answer as current.

## Official source registry

Runtime discovery is restricted to allowlisted HTTPS hosts and official index pages:

- Warzone: `https://www.callofduty.com/patchnotes`
- Black Ops 7: `https://www.callofduty.com/patchnotes`
- Battlefield 6: `https://www.ea.com/games/battlefield/battlefield-6/news`

The provider discovers the newest matching patch/update article from the official index on demand. Individual current article URLs are intentionally not hardcoded.

## Runtime behavior

Live HTTP is attempted only for intents that require current data:

- `META_CURRENT`
- `PATCH_CURRENT`

Normal coaching, settings, training, VOD and casual chat do not pay the network latency cost.

Flow:

1. classify the request;
2. if current data is required, query the official provider;
3. discover the latest official article;
4. validate the source and redirect host against the allowlist;
5. extract compact relevant patch evidence;
6. cache the official document for a short TTL;
7. mark evidence `VERIFIED_CURRENT` only after a successful live fetch;
8. let the AI reason over the evidence;
9. if any live verification step fails, use the existing currentness block instead of guessing.

## Meta semantics

Official patch notes verify official changes. They do not necessarily publish a universal ranked weapon meta.

For a current-meta question BLACK CROWN OPS therefore separates:

- **verified fact** — current official weapon/balance changes from the live patch source;
- **BCO inference/recommendation** — which weapon/loadout is likely strongest for the user's role/input/mode based on those changes and known context.

The bot must never call the inferred ranking an official developer ranking unless the source itself explicitly provides one.

## Security

The live provider:

- permits HTTPS only;
- permits only `callofduty.com` / `www.callofduty.com` / `ea.com` / `www.ea.com`;
- re-validates redirect destinations;
- does not follow arbitrary URLs supplied by users;
- caps downloaded HTML used by the parser;
- uses short network timeouts;
- fails closed to `UNKNOWN` knowledge on errors.

This prevents the live knowledge layer from becoming an SSRF/general-purpose fetch endpoint.

## Cost and performance

No additional paid API is introduced.

Default configuration:

```text
LIVE_KNOWLEDGE_ENABLED=1
LIVE_KNOWLEDGE_TTL_S=900
LIVE_KNOWLEDGE_TIMEOUT_S=6
```

A successful refresh normally needs one official index request and one official article request per game per TTL window. Subsequent current questions reuse the cached document while selecting request-specific evidence locally.

## Failure behavior

If Call of Duty or EA is unavailable, changes markup unexpectedly, redirects outside the allowlist, or times out:

- Telegram/WebApp remain operational;
- current/meta claims are blocked;
- static coaching and player intelligence remain available;
- no stale model memory is silently promoted to current truth.

## Future expansion

Phase 3 can later add additional trusted providers behind the same `KnowledgeProvider` boundary, for example:

- official playlist/status feeds;
- structured weapon-stat datasets with provenance;
- first-party APIs if published;
- a separately calibrated competitive-meta provider.

New providers must preserve source, retrieval time, confidence and failure isolation.
