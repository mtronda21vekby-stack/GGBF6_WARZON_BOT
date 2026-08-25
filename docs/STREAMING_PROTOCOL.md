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

## Voice stream

Voice uses the separate version `crown-voice-v1`. Every event contains `session_id`, `turn_id`, `speech_generation_id`, `event_id`, contiguous `sequence`, `timestamp`, and `segment_index`.

- `voice.started`: selected quality tier (`canonical` or `fallback`);
- `voice.audio`: `pcm_s16le`, sample rate, channels, ordered `chunk_index`, base64 payload and `is_final`;
- `voice.completed`: final completion only after all audio chunks;
- `voice.cancelled`: authenticated cancellation;
- `voice.failed`: typed non-sensitive failure code.

The client ignores duplicate event IDs and rejects a mismatched turn/generation, sequence gap, reordered chunk, unsupported codec, or completion-free stream. AudioClock remains client-authoritative once decoded PCM is actually audible.
