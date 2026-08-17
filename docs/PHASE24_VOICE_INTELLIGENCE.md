# BLACK CROWN OPS v24.1 — Duplex Voice Intelligence

## Mission

Make spoken Telegram messages a first-class BLACK CROWN input channel and make the spoken reply sound like a premium conversational AI rather than a utility TTS reader.

## Input runtime

The supported Telegram speech surfaces are:

- native `voice` notes;
- uploaded `audio` files;
- round `video_note` messages, using their audio track only.

The runtime path is:

`Telegram speech -> bounded temporary download -> contextual STT -> confidence gate -> same Router / Intelligence Core -> authoritative text final -> Smart Duplex voice output`

Primary STT is `gpt-4o-transcribe` with `gpt-4o-mini-transcribe` as the configured recovery model. The transcription prompt receives a bounded trusted server profile containing game, mode, role, platform, input, Zombies map and selected weapon vocabulary so mixed Russian/English FPS speech is recognized more reliably.

Video-note pixels are not analyzed by this path and are never represented as VOD analysis.

## Confidence boundary

When transcription confidence is available and sufficiently high, the transcript becomes the normal user message and enters the exact same Intelligence Core as typed text.

When confidence falls below the configured threshold:

1. the transcript is held outside player memory;
2. the bot shows what it heard;
3. the player chooses `USE TRANSCRIPT` or `RETRY`;
4. only an accepted transcript is allowed into analysis and persistent memory.

Unknown confidence fails open to the normal text path because the provider may not always expose token log probabilities.

## Smart Duplex

If the player has not explicitly selected a TTS mode:

- typed input -> text answer;
- spoken input -> text answer + spoken answer.

Explicit `OFF`, `AUTO` and `ON-DEMAND` remain authoritative.

Voice-to-voice replies receive a shorter spoken budget than the full text answer and skip unnecessary introductions or recaps of the player's question.

## Output voice

The cloud-first output path uses:

- steerable OpenAI synthetic TTS;
- selectable Marin / Coral / Shimmer / Cedar profiles;
- persona-aware TEAMMATE / COACH delivery;
- PRO / DEMON intensity without shouting or theatrical pitch manipulation;
- conversational code-switching for Russian plus FPS terminology;
- natural thought grouping instead of identical sentence-final cadence;
- transparent mastering without presence EQ or speech compression;
- mono 48 kHz Ogg/Opus at 72 kbit/s by default;
- Opus `application=audio` for better timbre preservation;
- local Piper as a resilient fallback.

No real-person voice imitation is used.

## Cost and abuse boundaries

STT and TTS use separate process-local budgets.

`stt` protects incoming transcription. `voice` protects outgoing synthesis. A normal voice-to-voice exchange therefore consumes one event from each relevant capability instead of double-counting against one generic voice bucket.

Default STT controls are configurable through:

- `STT_RATE_LIMIT_1M`;
- `STT_RATE_LIMIT_1H`;
- `STT_GLOBAL_RATE_LIMIT_1M`;
- `STT_GLOBAL_RATE_LIMIT_1H`.

## Security and privacy

- source audio exists only in a temporary directory and is deleted after the request;
- audio bytes are never persisted to Supabase;
- uncertain transcript text does not enter memory before confirmation;
- Telegram media size and duration are bounded;
- rate-limit telemetry contains counts, not user audio or full transcripts;
- logs contain request metadata rather than audio bytes;
- the existing Telegram webhook secret, update replay guard and AI abuse guard remain unchanged.

## Rollback

`VOICE_INPUT_ENABLED=0` disables incoming transcription without affecting typed text, outgoing TTS, VOD or webhook operation.

`VOICE_FOLLOW_INPUT_ENABLED=0` disables automatic voice-to-voice behavior while preserving manual TTS modes.

Release target: `24.1.0 / bco-duplex-voice-v24.1`.
