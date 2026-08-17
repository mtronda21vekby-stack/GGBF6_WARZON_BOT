# BLACK CROWN OPS v22 — Voice Studio Master

## Mission

Maximize perceived voice quality inside Telegram without adding another paid provider, cloning a real person, or weakening the existing local fallback.

## Signal path

```text
AI response
  -> speech normalization
  -> OpenAI steerable TTS to lossless WAV
  -> local Piper WAV fallback when cloud TTS fails
  -> BLACK CROWN Studio Master v2
  -> Ogg Opus 48 kHz mono
  -> Telegram voice note
```

Only one TTS generation call is required on the normal cloud path. The mastering stage is local ffmpeg processing and does not consume another AI request.

## Speech direction

The cloud TTS receives bounded delivery instructions that adapt to:

- TEAMMATE versus COACH;
- Normal / Pro / Demon;
- calm, hype, tilt and anxious states;
- direct voice-to-voice replies;
- short tactical callouts versus longer coaching debriefs.

The direction explicitly avoids announcer cadence, movie-trailer delivery, radio distortion, reverb, theatrical growl and imitation of a real named person.

## Speech normalization

`clean_tts_text` removes UI chrome, links, markdown and decorative glyphs while keeping meaningful paragraph boundaries for prosody.

Stable spoken forms are provided for recurring competitive terms including FPS, K/D, TTK, ADS, FOV, VOD, KBM, UAV, SMG, LMG, RPM, percentages, milliseconds and 1v1.

## Studio Master v2

Preferred mastering is measured two-pass EBU R128 normalization.

Target contract:

- integrated loudness: -16 LUFS;
- true peak: -1.0 dBTP;
- loudness range target: 5.5 LU;
- 48 kHz mono output;
- Opus VBR, default 72 kbps;
- high-pass filtering for low-frequency rumble;
- restrained warmth/presence EQ;
- mild dynamic compression;
- final peak limiter;
- short tail padding so Telegram playback does not clip the final phoneme.

If two-pass measurement is unavailable, the pipeline falls back to one-pass mastering and finally to clean Opus conversion rather than dropping the spoken reply.

## Reliability

The cloud TTS path keeps bounded network retries. If cloud synthesis fails, the existing Piper model produces the WAV and then passes through the same Studio Master chain.

Text remains authoritative. A voice failure never removes the written response.

## Configuration

Defaults:

```text
VOICE_PROVIDER=auto
VOICE_HIGH_FIDELITY_ENABLED=1
VOICE_LOCAL_FALLBACK_ENABLED=1
VOICE_OPENAI_MODEL=gpt-4o-mini-tts
VOICE_OPENAI_VOICE=cedar
VOICE_OPUS_BITRATE_KBPS=72
VOICE_MAX_CHARS=3200
VOICE_DUPLEX_MAX_CHARS=1800
```

Existing environment overrides remain valid.

## Privacy and safety

- API credentials are never embedded in audio or logged.
- No voice cloning is introduced.
- No real-person voice is requested or imitated.
- Telegram captions continue to disclose that the voice is synthetic AI audio.

## Validation

Tests cover:

- TTS direction and speed bounds;
- stable gaming-term pronunciation;
- paragraph preservation;
- loudness and limiter contracts;
- actual WAV -> Ogg Opus conversion;
- cloud-first/local-fallback behavior;
- release/readiness metadata;
- the full regression suite.

Release target:

```text
22.0.0 / bco-voice-studio-master-v22
```
