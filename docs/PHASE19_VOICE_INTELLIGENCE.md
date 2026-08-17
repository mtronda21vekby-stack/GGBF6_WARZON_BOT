# BLACK CROWN OPS v19 — Voice Intelligence

## Objective

Make Telegram voice notes a first-class input channel and improve speech output without creating a second AI brain.

Voice path:

```text
Telegram voice/audio
-> Telegram file download
-> OpenAI transcription
-> normalized text update
-> existing Router / Intent / Memory / Knowledge / Currentness / AI stack
-> normal final answer
-> optional high-fidelity TTS
```

The transcript is the user message. There is no separate voice-only response policy and no duplicated conversational memory.

## Input speech

- Telegram `voice` messages are supported.
- Telegram `audio` messages with audio mime types are also accepted.
- Default transcription model: `gpt-4o-mini-transcribe`.
- A domain prompt biases recognition toward Russian FPS speech, English gaming slang, game names and tactical abbreviations.
- Default maximum duration: 300 seconds.
- Default maximum file size: 12 MiB.
- Files are downloaded into a temporary directory and deleted after transcription.
- Raw audio is not written to player memory or Supabase.
- Only the resulting transcript enters the normal conversation pipeline.
- Voice-input abuse uses the existing bounded voice budget.

Rollback:

```text
VOICE_INPUT_ENABLED=0
```

## Output speech v19

High-fidelity output keeps the v17 hybrid architecture:

```text
OpenAI TTS -> mastering -> Telegram Opus
          \-> Piper local fallback
```

v19 refinements:

- persona-aware automatic timbre: TEAMMATE defaults to Cedar, COACH defaults to Marin unless the player explicitly selects a voice;
- more natural Russian breath groups and micro-pauses;
- stronger handling of English FPS terminology inside Russian speech;
- emotion-aware pacing for tilt/anxiety/hype;
- tighter DEMON cadence without shouting or theatrical roleplay;
- default Telegram Opus bitrate raised to 64 kbit/s;
- maximum speech text raised to 2000 characters while retaining sentence-aware trimming.

No real-person voice imitation is used.

## Reliability

- transcription retries once on 429/5xx/network failures;
- transcription errors fail locally and do not corrupt chat history;
- TTS still falls back to local Piper;
- typed messages remain unaffected if speech input fails;
- the production gate requires voice input, high-fidelity TTS and persistent Supabase readiness.

## Runtime flags

```text
VOICE_INPUT_ENABLED=1
VOICE_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
VOICE_INPUT_MAX_DURATION_S=300
VOICE_INPUT_MAX_BYTES=12582912
VOICE_OPUS_BITRATE_KBPS=64
```

## Release

```text
19.0.0 / bco-voice-intelligence-v19
```
