# BLACK CROWN OPS v20 — Duplex Voice Intelligence

## Objective

Turn Telegram voice notes into a first-class conversational channel instead of treating speech as a cosmetic TTS feature.

The v20 pipeline is:

```text
Telegram voice/audio
  -> bounded download
  -> gpt-4o-transcribe
  -> token confidence gate
  -> optional human confirmation
  -> existing Intelligence Core
  -> authoritative text response
  -> smart high-fidelity TTS reply
  -> Telegram Opus voice note
```

Typed and spoken requests use the same intent router, player profile, memory, currentness rules, knowledge context, response policy and anti-hallucination layer.

## Premium speech recognition

Primary STT model:

```text
gpt-4o-transcribe
```

Fallback:

```text
gpt-4o-mini-transcribe
```

The request supplies Russian as the language hint and a bounded FPS vocabulary prompt. English gaming terminology remains valid inside Russian speech.

When token log probabilities are available, v20 derives a length-stable confidence score using the geometric mean of token probabilities.

## Confidence trust boundary

A transcript above the configured threshold continues directly into the Intelligence Core.

A transcript below the threshold is **not** written into player memory and is **not** analyzed automatically. Telegram shows the detected phrase and two native actions:

```text
✓ USE TRANSCRIPT
↻ RETRY
```

The pending transcript is stored only in bounded in-process memory for a short TTL. Callback data contains a random nonce, never the transcript itself.

This prevents noisy speech-to-text from turning into tactical hallucination or contaminating long-term player intelligence.

## Smart Duplex

If a player has not explicitly selected a TTS mode:

```text
voice input -> text + voice answer
text input  -> text answer
```

An explicitly chosen `Voice OFF` always wins and disables automatic voice output. `AUTO` continues to voice every AI answer. `ON_DEMAND` remains manual.

Emergency rollback:

```text
VOICE_FOLLOW_INPUT_ENABLED=0
```

## Speech direction

High-fidelity TTS now receives content-aware direction:

- short tactical callout — compact breath pattern and decisive ending;
- medium tactical explanation — conversational context -> key point -> action arc;
- long coaching debrief — audible paragraph grouping and slower final third;
- ordered priorities — distinct pauses without sounding like a document reader.

Persona, brain mode and detected emotion continue to modify delivery only, never factual conclusions.

## Runtime configuration

```text
VOICE_INPUT_ENABLED=1
VOICE_TRANSCRIPTION_MODEL=gpt-4o-transcribe
VOICE_TRANSCRIPTION_FALLBACK_MODEL=gpt-4o-mini-transcribe
VOICE_TRANSCRIPTION_LANGUAGE=ru
VOICE_TRANSCRIPTION_CONFIDENCE_THRESHOLD=0.58
VOICE_TRANSCRIPT_CONFIRMATION_TTL_S=120
VOICE_FOLLOW_INPUT_ENABLED=1
VOICE_HIGH_FIDELITY_ENABLED=1
VOICE_LOCAL_FALLBACK_ENABLED=1
VOICE_OPUS_BITRATE_KBPS=64
```

No additional paid provider is introduced; the implementation reuses the existing OpenAI account and Piper local fallback.

## Privacy and safety

- audio is downloaded into an ephemeral temporary directory;
- audio is deleted immediately after transcription;
- transcripts are not logged;
- logs contain only duration, character count, model and confidence metadata;
- low-confidence text is not persisted before confirmation;
- size, duration and usage limits remain active;
- Telegram update replay protection remains active;
- text remains authoritative even if TTS fails.

## Validation

Tests cover:

- high-confidence voice -> text normalization;
- low-confidence transcript confirmation;
- retry/discard behavior;
- unknown-confidence compatibility path;
- duration limits;
- voice input rollback;
- confidence calculation;
- Smart Duplex behavior;
- explicit Voice OFF priority;
- duplex kill switch;
- content-aware TTS direction;
- release/readiness contract;
- full production regression suite.

Release target:

```text
20.0.0 / bco-duplex-voice-v20
```
