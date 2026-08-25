# Native CROWN API

Base namespace: `/api/v1/crown`

Protocol: `crown-realtime-v1`

All routes require `Authorization: Bearer <Supabase user JWT>`. The backend validates the token against Supabase GAME Auth, requires an Apple-authenticated subject for this native surface, resolves `black_crown_identities(provider='apple', provider_subject=<auth user id>)`, verifies the active canonical account, and only then creates a `CrownPrincipal`.

The client must never send or choose `black_crown_user_id`.

## Routes

- `POST /account-link/start` validates the Apple JWT and returns a short-lived Telegram verification URL without accepting an owner ID.
- `GET /account-link/{link_id}/status` is bound to the same authenticated Apple subject and returns `pending`, `linked`, `expired`, `cancelled`, or `conflict`.
- `DELETE /account-link/{link_id}` safely cancels a pending challenge owned by the authenticated Apple subject.
- `POST /bootstrap` returns canonical account ID, bounded Player Brain, entitlements, allowed capabilities and protocol version.
- `POST /session` creates or validates a client session identifier.
- `POST /turn` starts an SSE stream. The request uses the typed iOS `schemaVersion=1` envelope.
- `POST /cancel` cancels an active owner-matched session/turn.
- `GET /brain` returns a bounded Player Brain projection.
- `GET /skills/{skill_id}` returns one allow-listed, owner-scoped read projection. Available IDs are `player_brain_read`, `game_intel_read`, `loadout_read`, `training_summary_read`, and `history_summary_read`.
- `GET /voice/profile` returns non-secret canonical voice capabilities.
- `POST /voice/synthesize` emits an authenticated `crown-voice-v1` SSE stream of ordered `pcm_s16le` chunks.
- `POST /voice/cancel` cancels the owner-matched speech generation.
- `PATCH /brain` accepts only the controlled profile fields `current_goal`, `training_focus`, `weekly_focus`, and `playstyle`, and requires an `Idempotency-Key` UUID.

Native brain writes are value-setting operations. A bounded owner-scoped replay registry prevents a repeated idempotency key from executing twice and returns `X-Crown-Replay: 1`. Persistent cross-instance mutation receipts are not yet implemented; non-idempotent and sensitive skills remain unavailable to native clients.

## Fail-closed behavior

- missing/invalid/expired session: `401`;
- authenticated identity not linked to a canonical account: `403 canonical_link_required`;
- account-link ownership conflict: `409 account_link_conflict`;
- expired account-link challenge: `410 account_link_expired`;
- ownership mismatch: `403`;
- unlisted or mutation skill: `404 capability_unavailable`;
- active duplicate turn: `409`;
- schema mismatch: `409 protocol_mismatch`;
- provider/internal generation failure: typed `turnFailed` without stack trace.

No service-role key, model credential or universal bearer token is returned to the iPhone.

## Shared skill result

Skill responses include `skill_id`, `title`, `summary`, structured `blocks`, bounded compatibility `data`, `freshness_timestamp`, `warnings`, and `next_cursor`. History accepts `cursor` and `limit` (`1...50`). The canonical block vocabulary is `text`, `metric`, `loadout`, `comparison`, `timeline`, `warning`, `evidence`, and `action_group`.

## Voice request

The synthesize request carries `sessionID`, `turnID`, `speechGenerationID`, `requestID`, `segmentIndex`, `locale`, and spoken `text`. Display content is never inferred from audio. The server applies its canonical spoken-text cleaner, uses the existing high-fidelity provider when configured, and can use the existing Russian Piper fallback. English is not falsely routed to the Russian fallback.

This transport is currently buffered PCM chunk streaming: the provider finishes one bounded spoken segment before PCM chunks are emitted. The contract is incremental and cancellation-safe, but it is not advertised as provider-native low-latency audio streaming.
