# BLACK CROWN OPS v23 — Natural Voice

## Objective

Fix the primary product complaint with v22 voice output: the speech was technically clean but could sound over-processed, rushed and synthetic.

v23 changes the output philosophy from **broadcast mastering** to **transparent conversational speech** while preserving the already-working Telegram voice-message understanding pipeline.

## Voice input remains authoritative

Telegram voice/audio input continues through:

```text
Telegram voice note
→ bounded file download
→ gpt-4o-transcribe
→ gpt-4o-mini-transcribe fallback
→ confidence gate
→ same ConversationService / Intelligence Core as text
→ persistent final player memory
```

Low-confidence transcripts are not silently treated as reliable user intent. The existing confirmation boundary remains in place.

## New default voice

The default cloud voice changes from `cedar` to `marin`.

Player selection remains authoritative and is persisted in the profile. Persona selection no longer silently swaps the selected timbre.

Voice Studio choices:

- `MARIN · SOFT` — primary soft modern profile;
- `CORAL · WARM` — warm alternative;
- `SHIMMER · LIGHT` — lighter, clearer alternative;
- `CEDAR · TACTICAL` — lower tactical alternative.

These are synthetic AI voices. BLACK CROWN does not claim that a built-in voice has a biological gender and does not imitate a real person. The UI describes perceived delivery characteristics instead.

## Natural cloud mastering

v22 sent the OpenAI WAV through the same rescue mastering architecture used to improve local Piper speech. That chain included strong loudness normalization, EQ and compression.

v23 splits the two paths:

### OpenAI cloud

```text
OpenAI WAV
→ 45 Hz safety high-pass
→ peak safety limiter
→ 48 kHz mono
→ single Ogg Opus encode
```

No cloud presence boost, compressor or loudness normalization is applied. The neural model's native timbre, dynamics and micro-prosody are preserved.

### Piper fallback

The existing stronger v22 studio/rescue mastering remains available only for the local Piper fallback, where corrective processing is useful.

## Speech direction

The OpenAI instruction block is intentionally shorter and less prescriptive.

Priorities:

- fluent conversational Russian;
- one-to-one close speech;
- connected phrases and natural micro-pauses;
- no narrator / announcer / trailer / radio performance;
- no artificial pitch lowering;
- no over-enunciation;
- no real-person imitation;
- tactical terminology remains accurate.

TEAMMATE and COACH now modify delivery lightly instead of redefining the voice.

Speed stays near the model-native `1.0x` timing instead of deliberately pushing TEAMMATE above `1.04x`.

## Smart Duplex

When the player sends a Telegram voice note and has not explicitly selected another TTS delivery mode, Smart Duplex continues to return the normal authoritative text answer plus a synthesized voice reply.

The Voice panel explicitly reports that incoming voice notes are understood through STT and sent to the same Intelligence Core.

## Reliability

Cloud generation failure still falls back to local Piper. A TTS failure never prevents the authoritative text response.

No new external provider, database or secret is required.

Release target:

```text
23.0.0 / bco-natural-voice-v23
```
