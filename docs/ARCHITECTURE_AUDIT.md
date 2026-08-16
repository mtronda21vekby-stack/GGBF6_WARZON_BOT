# BLACK CROWN OPS — Architecture Audit

## Production runtime

### Telegram

`app/webhook.py`
→ `app.core.router.Router`
→ shared `ConversationService`
→ `BrainEngine`
→ `AIHook`
→ OpenAI-compatible Chat Completions
→ Telegram adapter

### Telegram Mini App

`app/webhook.py`
→ `app.webapp.webapp_router`
→ shared `ConversationService`
→ `BrainEngine`
→ `AIHook`

The Telegram and Mini App paths intentionally converge on the same conversation/intelligence boundary.

## Active modules

- `app/webhook.py` — FastAPI production entrypoint and Telegram webhook.
- `app/core/router.py` — deterministic Telegram menu/navigation orchestration and free-form chat handoff.
- `app/adapters/telegram/*` — Bot API transport/types.
- `app/services/brain/engine.py` — intelligence orchestration.
- `app/services/brain/ai_hook.py` — canonical production model generation boundary.
- `app/services/brain/intents.py` — deterministic intent routing.
- `app/services/brain/prompt_builder.py` — authoritative prompt construction.
- `app/services/brain/response_policy.py` — intent-specific depth/format/uncertainty policy.
- `app/services/brain/knowledge_context.py` — trusted knowledge selection and future provider boundary.
- `app/services/storage/*` — storage interface plus in-memory production fallback.
- `app/services/profiles/*` — backward-compatible profile plus optional player-intelligence fields.
- `app/worlds/warzone`, `bo7`, `bf6`, `zombies` — deterministic game-world presets.
- `app/webapp/*` — Telegram Mini App routes/static delivery/security boundary.

## Partially active / reusable

- `app/content/catalog.py` and `app/content/data/*`
  - structured game settings/training data with source/last_updated metadata;
  - now consumed through `StaticKnowledgeProvider` where relevant.
- `app/services/brain/knowledge.py`
  - generic tactical rules; usable as verified static principles, not live meta.
- `app/services/brain/loadouts.py`
  - role-level weapon-class guidance; not attachment-level current meta.
- `app/services/brain/patterns.py`, `decision.py`, `detector.py`, `dialogues.py`, `coach.py`
  - useful concepts, but not all are in the active free-form generation path.

## Legacy / duplicate architecture

These modules are not the production path starting at `app/webhook.py` and should not be deleted until a dedicated cleanup verifies all imports and external entrypoints:

- `app/brain/brain_v3.py` — explicit placeholder implementation.
- `app/brain/memory.py` — separate older memory implementation.
- `app/services/ai/openai_client.py` — separate Responses API client.
- `app/services/llm/client.py` — generic OpenAI-compatible client.
- `app/services/brain/llm.py` — another chat-completions client.
- `app/services/brain/prompts.py` — older prompt builder.
- `app/usecases/*` — alternate/older application flow not wired by the current webhook production entrypoint.

## Unsafe cleanup candidates

Do not delete in this PR:

- old LLM clients;
- `app/brain/*`;
- `app/usecases/*`;
- older prompt/coach modules.

Reasons:
1. repository history contains multiple architectural generations;
2. external scripts/imports may still reference them;
3. cleanup provides little user value compared with the risk of a production regression.

A future cleanup PR should use import graph/static search plus smoke tests before deletion.

## Current technical debt

1. `app/core/router.py` remains very large and owns too many deterministic flows.
2. Persistent storage is not yet configured; the in-memory backend is intentionally a fallback.
3. Current meta/patch data has no live provider, so currentness is hard-gated rather than guessed.
4. Real VOD media/vision analysis is not implemented; only text/timestamp analysis is honest today.
5. Premium billing remains UI/product scaffolding, not an entitlement system.
6. Some world data is dated and third-party sourced; freshness metadata must be respected.
7. Legacy/duplicate modules remain in-tree pending safe cleanup.

## Target architecture

Incrementally move toward:

- Router = deterministic Telegram/UI orchestration.
- ConversationService = shared free-form intelligence entrypoint.
- BrainEngine = intent + knowledge + policy + generation orchestration.
- PromptBuilder = one authoritative prompt composition path.
- KnowledgeProvider = pluggable static/live sources.
- Storage = pluggable memory/PostgreSQL/Supabase/Redis.
- ProfileService = stable player identity/intelligence model.
- Training/VOD services = dedicated domain boundaries.

The migration is intentionally incremental: existing menus, worlds, webhook and Mini App remain operational while new intelligence capabilities are added behind compatible interfaces.
