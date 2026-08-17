# BLACK CROWN OPS v24 — Voice Intelligence

## Mission

Make Telegram voice notes a first-class input channel rather than a separate utility.

## Runtime

Telegram voice/audio now follows:

`Telegram audio -> bounded download -> contextual STT -> confidence gate -> same Router / Intelligence Core -> text final -> Smart Duplex voice output`

The transcription prompt is biased with trusted server-side player context such as game, mode, role, platform, input, Zombies map and a bounded preferred-weapon list. This improves recognition of mixed Russian/English FPS vocabulary without allowing the audio model to invent tactical facts.

## Confidence boundary

High-confidence transcripts continue immediately through the normal Intelligence Core.

When token confidence is available and falls below the configured threshold, the transcript is held outside player memory and shown for explicit confirmation. Only `USE TRANSCRIPT` converts it into a synthetic text update.

## Output voice

v24 preserves the v23 natural voice architecture:

- OpenAI steerable natural TTS first;
- Marin / Coral / Shimmer / Cedar selectable synthetic profiles;
- transparent cloud mastering;
- 72 kbit/s Telegram-native Opus;
- local Piper fallback;
- SMART DUPLEX: voice input receives voice + text unless the player explicitly selected another TTS mode.

No real-person voice imitation is used.

## Security / privacy

- voice files live only in a temporary directory;
- audio is not persisted to Supabase;
- no transcript enters memory before the confidence boundary accepts it;
- Telegram file size and duration are bounded;
- existing voice abuse limits remain active;
- logs contain metadata, not audio bytes or full transcripts.

## Rollback

`VOICE_INPUT_ENABLED=0` disables incoming voice transcription without affecting text, TTS, VOD or Telegram webhook operation.

Release target: `24.0.0 / bco-voice-intelligence-v24`.
