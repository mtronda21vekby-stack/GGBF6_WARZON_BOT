# BLACK CROWN OPS — AAA Roadmap

## Phase 1 — Intelligence Core v1

- deterministic intent routing;
- centralized prompt construction;
- response policy by intent;
- knowledge provenance/freshness states;
- anti-hallucination currentness gate;
- shared Telegram/Mini App conversation service;
- player intelligence schema;
- storage abstraction with in-memory fallback;
- quality/evaluation test foundation.

## Phase 2 — Persistent Player Intelligence

Add a persistent storage adapter without changing Router/BrainEngine contracts.

Suggested entities:

- users/player_profiles;
- conversation summaries;
- recurring mistakes;
- training sessions;
- match/progression events;
- derived player scores;
- weekly objectives.

Requirements:

- server-side source of truth;
- migrations;
- retention/privacy policy;
- graceful fallback if persistent storage is unavailable;
- no LLM summarization on every message.

## Phase 3 — Live Game Intelligence

Implement trusted live providers behind `KnowledgeProvider`.

Priority sources:

1. official patch notes;
2. official playlist/ranked announcements;
3. official weapon balance changes;
4. curated competitive/meta sources only where official data is insufficient.

Add:

- provider timestamps;
- source URLs/IDs;
- freshness TTL;
- conflict handling;
- `VERIFIED_CURRENT` only when evidence satisfies freshness policy;
- per-game source strategy.

No fragile scraping inside request latency.

## Phase 4 — Real VOD Intelligence

Extend `VODAnalysisService` from text/timestamps to media.

Capabilities:

- video upload/attachment ingestion;
- timestamp extraction;
- frame/clip selection;
- fight/death classification;
- position/cover/rotation review;
- user-visible distinction between observed frame evidence and inferred advice.

Never claim frame analysis when only text was supplied.

## Phase 5 — Voice

Optional free/self-hosted TTS boundary.

Modes:

- OFF;
- ON_DEMAND;
- AUTO.

Telegram output:

- text remains available;
- optional OGG/Opus voice message;
- generated voice must be an original synthetic profile, not an imitation of a real person.

TTS should remain replaceable and must not be hard-coupled to the intelligence core.

## Phase 6 — Premium Command Center

Mini App becomes the player intelligence dashboard:

- profile;
- aim/movement/positioning/decision/comms scores;
- recurring mistakes;
- recent sessions;
- weekly focus;
- training plan;
- progress charts;
- VOD reports;
- source/freshness badges for current game intelligence.

Premium should mean deeper analysis and persistence, not decorative typography.

## Phase 7 — AAA Product Quality

- larger offline evaluation suite;
- answer feedback loop;
- latency budgets;
- model/provider fallback strategy;
- structured error taxonomy;
- observability dashboards;
- abuse/rate limits;
- entitlement/payment hardening;
- regression gates before production merge;
- disaster recovery and deployment playbook.
