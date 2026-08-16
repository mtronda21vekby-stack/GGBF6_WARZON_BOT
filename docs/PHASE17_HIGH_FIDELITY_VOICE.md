# BLACK CROWN OPS v17 — High-Fidelity Tactical Voice

## Objective

Replace the single flat local Piper delivery with a resilient voice stack that sounds more natural in Russian, supports tactical personas, and never makes the text bot dependent on one external speech provider.

## Runtime strategy

The production strategy is `cloud_first_local_fallback`:

1. Generate a steerable high-fidelity WAV through the OpenAI Audio API when `OPENAI_API_KEY` and high-fidelity voice are configured.
2. If the cloud request is unavailable, rate-limited, times out, or returns invalid audio, synthesize the same speech locally with Piper.
3. Run either source through the same BLACK CROWN mastering and Telegram Opus pipeline.

A speech failure never blocks the original text response.

## Voice direction

The service derives performance instructions only from safe player profile fields.

### TEAMMATE

- slightly brisk;
- direct and concise;
- calm squad communication;
- no shouting or fake radio distortion.

### COACH

- measured pace;
- analytical authority;
- stronger emphasis on cause and next action;
- warmer spectral balance.

### DEMON core

- restrained intensity;
- decisive phrasing;
- no theatrical aggression.

The prompt explicitly prevents impersonation of a named real person.

## Selectable voices

The Telegram voice panel exposes:

- `CEDAR` — focused tactical delivery;
- `MARIN` — softer, more conversational delivery;
- `Тест голоса` — a short preview independent of AUTO/ON-DEMAND mode.

The selected built-in synthetic voice is persisted as `tts_voice` in the player profile.

## Speech normalization

Before synthesis, the system:

- removes BLACK CROWN message chrome, URLs, code blocks, Markdown and emoji;
- preserves natural sentence punctuation;
- adds explicit Russian pronunciation for common FPS terms such as FPS, K/D, TTK, ADS, FOV, VOD, KBM, percentages and milliseconds;
- truncates only at a stable sentence boundary when possible.

## Audio mastering

Every WAV is converted to Telegram-compatible mono Opus at 48 kHz with:

- 48 kbit/s variable bitrate;
- high-pass and low-pass filtering;
- persona-aware presence/warmth EQ;
- gentle compression;
- loudness normalization;
- peak protection;
- short tail padding to avoid clipped final consonants.

If a bundled ffmpeg build does not support the full filter chain, conversion automatically retries without mastering instead of dropping the voice message.

## Transparency

Every delivered voice message carries a visible synthetic-AI disclosure. The voice panel repeats that disclosure. No custom voice cloning or real-person impersonation is implemented.

## Security and privacy

- `OPENAI_API_KEY` remains a Render server secret and is never committed.
- Audio responses are bounded by a strict byte limit and validated as RIFF/WAVE before processing.
- Logs contain provider and voice identifiers, not the spoken text.
- The remote backend receives only the cleaned text selected for synthesis.

## Rollback

Force the fully local voice path without changing user profiles:

```text
VOICE_HIGH_FIDELITY_ENABLED=0
```

or:

```text
VOICE_PROVIDER=piper-only
```

Disable the local fallback only when the cloud path has been independently verified:

```text
VOICE_LOCAL_FALLBACK_ENABLED=0
```

## Release

```text
17.0.0 / bco-voice-hifi-v17
```
