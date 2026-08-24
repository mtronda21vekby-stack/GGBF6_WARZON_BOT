# BLACK CROWN capability inventory

Audit scope: the production FastAPI/Telegram/Web runtime under `app/`. Classification describes authority, not UI placement. Only entries explicitly listed in `CrownSkillRegistry` are available to native iOS.

| Capability group | Classification | Current authority / adapter | Native exposure |
|---|---|---|---|
| Conversation, bounded session context, response composition, personality/model routing | `CORE_READ` | `CrownCore` -> `ConversationService` -> `BrainEngine` | `conversation` |
| Player Brain profile, summary, derived intelligence | `CORE_READ` | `CrownCore`, `PlayerMemoryService`, canonical storage | `player_brain_read` |
| Game knowledge, intents, worlds, seasonal/live official context | `CORE_READ` | `app/services/brain/*`, `app/worlds/*` | bounded `game_intel_read` |
| Static role/loadout knowledge | `CORE_READ` | `app/services/brain/loadouts.py`, world presets | `loadout_read` |
| Training-session summary | `CORE_READ` | canonical storage and training services | `training_summary_read` |
| Bounded conversation-history summary | `CORE_READ` | shared canonical/legacy-compatible store | `history_summary_read` |
| Controlled goal, focus and playstyle profile patch | `CORE_MUTATION` | `CrownCore.patch_brain`, server-resolved owner, idempotency key | compatibility endpoint only; not a skill |
| Player-memory extraction, episodes, mistake/progression writes | `CORE_MUTATION` | `PlayerMemoryService` inside trusted conversation | indirect server policy only |
| Training plans and session lifecycle | `CORE_MUTATION` | `TrainingService`, `CrownSessionCycleService` | not exposed |
| Entitlement reads/link challenges/unlink | `SENSITIVE` | entitlement services and verified website/Telegram boundaries | bootstrap read only; mutations not exposed |
| Account identity, merge/link and canonical resolution | `SENSITIVE` | Supabase GAME plus server identity services | resolution only; verified external link flow required |
| VOD upload, frame analysis and evidence fusion | `SERVER_TOOL` | VOD services and Telegram/Web ingress | not exposed |
| LLM generation and official-game-data fetches | `SERVER_TOOL` | server settings, AI hook/client and knowledge services | only through Core conversation |
| Voice STT/TTS/Piper/provider audio | `SERVER_TOOL` | voice services and Web/Telegram adapters | voice profile contract only; native audio remains client-side |
| Operator intelligence, missions, longitudinal strategy | `SERVER_TOOL` | operator-intelligence services | context may inform Core; direct tools not exposed |
| Rate limiting, replay guards, policy and observability | `SERVER_TOOL` | security/observability services | enforced server-side |
| Telegram commands, callbacks, keyboards and rich messages | `TELEGRAM_PRESENTATION` | router, use cases, UI, Telegram adapters | never |
| Telegram voice ingress and bot delivery | `TELEGRAM_PRESENTATION` | voice Telegram controller and client | never |
| Mini App HTML/JS, command center, quality UI and Web voice transport | `WEB_PRESENTATION` | `app/webapp` and static assets | never |
| Admin console, production verification and readiness diagnostics | `SENSITIVE` | admin/observability services | never |
| Zombies navigation/preset presentation and legacy router branches | `LEGACY` | legacy router and world presentation | not exposed; knowledge remains usable through Core |
| Historic `app/brain` and compatibility router implementations | `LEGACY` | compatibility source retained for production behavior | never directly |

## Native allow-list invariant

The native API never dynamically imports a handler by client input. `GET /api/v1/crown/skills/{skill_id}` first checks `CrownSkillRegistry`, then resolves data through the authenticated `CrownPrincipal`. Every projection uses `principal.legacy_owner_id` only after verifying the profile projects the same server-resolved `black_crown_user_id`. Unknown, write, sensitive and presentation capabilities fail closed.

No capability in this inventory authorizes a client-supplied canonical user ID, service-role credential, provider token or arbitrary tool execution.
