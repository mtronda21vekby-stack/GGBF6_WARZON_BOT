# CROWN Core

`app/crown_core` is the surface-neutral boundary around the production BLACK CROWN conversation system.

```text
Telegram adapter ─┐
Web adapter ──────┼─> CROWN Core ─> ConversationService ─> BrainEngine / AIHook
iOS API ──────────┘       │
                           ├─> shared Player Brain and history in Supabase GAME
                           └─> shared VoiceService and CrownVoiceProfile
```

The extraction deliberately reuses the existing `ConversationService`, `BrainEngine`, prompt builder, response policy, AI provider configuration, usage guard, Player Brain and persistence. It does not implement a second model client or personality.

## Boundaries

- `CrownPrincipal` is created only after server-side identity resolution. Core never trusts a client-supplied `black_crown_user_id`.
- `CrownTurnRequest` contains canonical identity, surface, session, turn, locale and route. It contains no Telegram SDK object.
- existing Telegram and Mini App routes remain compatibility adapters and invoke the same Core facade;
- native iOS calls the versioned API adapter;
- `CrownSkillRegistry` is an allow-list. Native exposes only conversation and the five audited read projections: Player Brain, game intelligence, loadout, training summary and history summary;
- `CrownSkillResult` is surface-neutral and carries typed blocks, bounded data, warnings, freshness and pagination without Telegram markup;
- the native voice adapter calls the same `VoiceService` used by Telegram/Web before their OGG presentation packaging. Provider selection, canonical voice direction and Piper fallback remain server-owned;
- provider credentials, Supabase service credentials and personality configuration remain server-only.

The current database still uses Telegram `chat_id` as the storage owner for several legacy BCO tables. Identity resolution therefore maps the canonical UUID to its active Telegram identity internally. This compatibility projection is not a second product identity. Removing the legacy storage key requires a separately reviewed additive database evolution.

## Cancellation and idempotency

`ActiveTurnRegistry` owns active native generations by `session_id` and `turn_id` and checks canonical ownership. An SSE disconnect or authenticated `/cancel` request sets the same cancellation signal. The provider callback observes that signal and terminates generation; incomplete turns are never added to replay storage. Completed event streams are replayable for the same canonical owner and turn, preventing retry-driven duplicate generation. Controlled profile patches use a bounded owner-scoped idempotency registry; a repeated key returns the original result without applying a second mutation.

`NativeVoiceRegistry` separately owns speech generations by canonical owner, `session_id`, `speech_generation_id`, and idempotent `request_id`. Native barge-in cancels the provider task, ends the event stream, and makes late PCM unavailable to the client. The client independently rejects stale generation and chunk sequence data.

## One production runtime

`app/webhook.py` constructs one `ConversationService`, wraps it once in `CrownCore`, and injects that same instance into the Telegram `Router`, Mini App `bind_runtime`, and `NativeCrownAPI`. Personality, model policy, `BrainEngine`, usage guard, Player Brain, game knowledge and persistence therefore remain server-owned and shared. Surface SDK objects are converted before entering the Core contract.
