# Native CROWN API

Base namespace: `/api/v1/crown`

Protocol: `crown-realtime-v1`

All routes require `Authorization: Bearer <Supabase user JWT>`. The backend validates the token against Supabase GAME Auth, requires an Apple-authenticated subject for this native surface, resolves `black_crown_identities(provider='apple', provider_subject=<auth user id>)`, verifies the active canonical account, and only then creates a `CrownPrincipal`.

The client must never send or choose `black_crown_user_id`.

## Routes

- `POST /bootstrap` returns canonical account ID, bounded Player Brain, entitlements, allowed capabilities and protocol version.
- `POST /session` creates or validates a client session identifier.
- `POST /turn` starts an SSE stream. The request uses the typed iOS `schemaVersion=1` envelope.
- `POST /cancel` cancels an active owner-matched session/turn.
- `GET /brain` returns a bounded Player Brain projection.
- `PATCH /brain` accepts only the controlled profile fields `current_goal`, `training_focus`, `weekly_focus`, and `playstyle`, and requires an `Idempotency-Key` UUID.

Native brain writes are value-setting operations and therefore idempotent for the same payload. Persistent mutation receipts are not yet implemented; non-idempotent skills remain unavailable to native clients.

## Fail-closed behavior

- missing/invalid/expired session: `401`;
- authenticated identity not linked to a canonical account: `403 canonical_link_required`;
- ownership mismatch: `403`;
- active duplicate turn: `409`;
- schema mismatch: `409 protocol_mismatch`;
- provider/internal generation failure: typed `turnFailed` without stack trace.

No service-role key, model credential or universal bearer token is returned to the iPhone.

