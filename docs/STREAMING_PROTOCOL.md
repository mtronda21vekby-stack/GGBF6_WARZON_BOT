# CROWN realtime streaming protocol

Version: `crown-realtime-v1`

The native endpoint emits server-sent events containing:

- `schemaVersion`;
- `protocolVersion`;
- `sessionID`;
- `turnID`;
- unique `eventID`;
- contiguous `sequence`;
- Unix `timestamp`;
- typed event payload.

Event types are `routeSelected`, `turnStarted`, `textDelta`, `spokenContent`, `performanceIntent`, `turnCompleted`, `turnCancelled`, and `turnFailed`. Vendor DTOs are never exposed.

`textDelta` is display content. `spokenContent` is a normalized, ordered sentence segment with Markdown and URLs removed. Completion means all accumulated display and spoken content has been emitted.

The iOS client rejects mismatched sessions/turns, unsupported versions, sequence gaps and unknown event types. Duplicate `eventID` values are ignored. A cancelled turn is not cached as completed and cannot resume after a new turn.

