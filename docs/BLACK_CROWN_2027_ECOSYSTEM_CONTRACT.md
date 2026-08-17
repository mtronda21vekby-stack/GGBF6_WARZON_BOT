# BLACK CROWN // 2027 — Unified Ecosystem Contract

Status: product/architecture directive. This document constrains future implementation; it does not claim every target below is already shipped.

## Product invariant

BLACK CROWN is one Artificial Competitive Intelligence system with multiple clients.

```text
BLACK CROWN
  CROWN IDENTITY CORE
  CROWN INTELLIGENCE CORE
    ├─ Website — central account/product hub
    ├─ Telegram Bot — conversational/proactive interface
    └─ Telegram Mini App — visual Telegram client
```

Non-negotiable target:

**ONE USER · ONE BLACK CROWN ACCOUNT · ONE PLAYER BRAIN · ONE SUBSCRIPTION · ONE INTELLIGENCE CORE · MULTIPLE INTERFACES**

Clients are not sources of truth. Shared backend/core services and Supabase GAME are the authoritative state boundary.

## Canonical identity

The long-term canonical identifier is `black_crown_user_id`. Telegram is an identity provider/channel, not the permanent primary key.

```text
black_crown_user_id
├─ telegram_user_id
├─ website_auth_user_id
├─ email_identity
├─ future_apple_identity
├─ future_google_identity
├─ future_xbox_identity
├─ future_playstation_identity
└─ future_steam_identity
```

New product data should converge on the canonical ID. Existing Telegram-keyed data must be migrated safely; do not destructively rewrite production history merely to satisfy the target model.

Account linking requires one-time short-lived tokens/codes, replay protection, server-side Telegram validation, explicit confirmation, rate limiting and audit events. Never trust username, nickname, browser state or unverified Mini App data as identity. Never silently merge conflicting accounts. Conflict resolution must preserve Player Brain, history, entitlement and squad membership and produce an audit trail.

## Website role

The website is the central product/account hub, not a landing page. Long term it owns account management, CROWN Profile, connected identities, subscription, privacy, data export/deletion, expanded analytics, Player Brain/history, squads and connected platforms.

**Do not redesign or rebuild the website automatically when Bot/Mini App changes.** Website changes during Telegram development are limited to account synchronization, shared API contracts, critical account flows, compatibility and security. Visual site development happens in separate deliberate passes.

## Shared state

Website, Bot and Mini App must resolve the same authoritative:

- CROWN Profile and Player Brain;
- subscription and capabilities;
- preferences/modes/goals;
- Personal Meta;
- War Room;
- After Action and match history;
- progression;
- squad state;
- notifications and privacy settings;
- voice profile.

Local/session/browser state is cache or UI state only. Critical state must not live only in Telegram session, localStorage, cookies, conversation text or divergent client tables.

## Telegram product rule

Bot + Mini App are one synchronized Telegram product.

Every material Telegram capability requires review of:

1. shared backend contract;
2. Bot experience;
3. Mini App experience;
4. unified identity/account impact;
5. entitlement impact;
6. Player Brain impact;
7. backward compatibility;
8. whether the website needs only compatibility or an explicit account-flow change.

Capability parity does not mean identical UI. Bot should favor dialogue, voice, alerts and fast actions; Mini App should handle visual/complex workflows. Deep links and shared state should allow cross-client continuation.

## API and release discipline

CROWN API changes must prefer additive/backward-compatible schemas, explicit contracts, capability negotiation, feature flags, safe defaults, migration windows and graceful degradation. Bot, Mini App and Website may deploy at different times.

A Telegram capability is not done until shared backend, unified account, Bot, Mini App, entitlements, synchronization and backward compatibility are checked. The website does not need the same visual feature, but must remain account/data/subscription/API compatible.

## Unified analytics

Analytics must converge on `black_crown_user_id`, not count the same human separately per client. Events should support privacy-safe cross-client journey analysis: entry surface, value event, Bot→Mini App continuation, Mini App→Bot return, account friction, recommendation use and outcome. Telegram header/member counts are not DAU/WAU/MAU.

## Voice is first-class

CROWN Voice is an interface, not a TTS add-on.

Target pipeline:

```text
USER VOICE
→ SPEECH UNDERSTANDING
→ INTENT + CONTEXT (+ reliable urgency/emotion only when justified)
→ CROWN INTELLIGENCE
→ RESPONSE PLANNING
→ VOICE PERFORMANCE ENGINE
→ STREAMING SPEECH
```

Voice preference belongs to the BLACK CROWN account, never to an individual client. Target profile:

- `voice_identity`: male | female;
- response: off | manual | automatic;
- language: auto | explicit;
- speed: adaptive | override;
- detail: brief | balanced | deep;
- interruption: enabled | disabled.

### Dual CROWN identity

`CROWN // MALE` and `CROWN // FEMALE` are first-class presentation identities of the same intelligence entity. They share the same Player Brain, memory, capabilities and modes. Neither may imitate a real person.

Male target: adult, deep but natural, controlled, tactical, intelligible, no artificial Batman/trailer treatment.

Female target: adult tactical intelligence officer; controlled, intelligent, calm, confident, slightly dark, precise, premium, restrained, never childish/overly seductive/generic-assistant.

Voice identity changes delivery, not intelligence quality.

## Voice Performance Engine

Speech rendering must use structured context such as interaction mode, brain mode, urgency, message type, confidence, response length, language and pronunciation hints. TEAMMATE is fast/direct; COACH is deliberate/analytical; WAR ROOM is concise mission-briefing cadence; DEMON is colder and denser without villain theatrics.

Text and speech are separate presentation representations over the same underlying intelligence. Never read Markdown/UI chrome aloud.

## Voice platform architecture

Voice must evolve toward provider abstraction and low-latency streaming rather than a permanent single-provider dependency. Provider selection is based on quality, language, latency, expressiveness, consistency, cost, availability and streaming support.

Required long-term capabilities include streaming STT/TTS, VAD/turn detection, interruption/barge-in, cancellation, continuation and explicit latency telemetry. Primary user metric: **time to first audio**.

Maintain a centralized gaming pronunciation layer for game, weapon, attachment, map, mode, squad/user and esports terms. Do not scatter pronunciation hacks through Telegram handlers.

Voice failures degrade primary → secondary/local fallback → text. Never hold the user indefinitely for speech retries.

Voice configurations are versioned (`crown_male_vN`, `crown_female_vN`) to support controlled migration, A/B evaluation and rollback.

## Multilingual voice

Voice follows the same ecosystem locale authority as text. Russian, English and mixed FPS code-switching are first-class design cases. Do not hardcode Russian speech instructions into a provider adapter when the resolved account/conversation language is English.

## Voice privacy and observability

Separate raw audio, transcript and derived memory. Do not retain raw audio indefinitely by default and do not turn every utterance into permanent Player Brain memory.

Measure STT latency/confidence, TTS latency, time-to-first-audio, provider/fallback failures, interruptions, completion, usage, language detection and cost without placing sensitive audio/transcripts in telemetry.

## Current implementation compatibility

Existing production account linking and Premium entitlement code remains the compatibility base until a canonical identity migration is designed and verified. Linking does not grant Premium; entitlement remains server-authoritative. Existing website account bridge must not be replaced by a destructive rewrite.

Existing voice stack remains the compatibility base while the dual-identity/performance/provider architecture is introduced incrementally. Preserve rollback and text fallback.

## Definition of done for future work

Before shipping a shared capability answer:

- What changes for the canonical account?
- What changes for Player Brain?
- What is the Bot experience?
- What is the Mini App experience?
- Does the website require a compatibility/account change, or no change?
- Can any client create divergent state?
- Are entitlements server-authoritative?
- Does the API tolerate staggered deployments?
- Is cross-client continuity tested?
- If voice is involved, are male/female identity, language, fallback, latency and privacy considered?

The interfaces may differ. **Identity, memory, intelligence, subscription and history remain one system.**
