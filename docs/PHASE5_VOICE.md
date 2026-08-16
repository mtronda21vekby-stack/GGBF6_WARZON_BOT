# BLACK CROWN OPS — Phase 5 Voice/TTS

## Goal

Add optional native Telegram voice replies without another paid API and without making TTS a dependency for core bot availability.

## Provider

Phase 5 uses Piper (`piper-tts==1.4.2`) on CPU.

Default voice model:

- `ru_RU-denis-medium`
- Russian, medium quality, 22.05 kHz source model
- model dataset license: CC0
- model is downloaded from the pinned `rhasspy/piper-voices` v1.0.0 asset path
- ONNX model SHA256 is verified before use

The model is **not** committed to GitHub. `.bco_voice/` is ignored.

## Modes

Player profile field: `tts_mode`

- `OFF` — text only (default)
- `AUTO` — every new AI assistant turn is followed by a Telegram voice message
- `ON_DEMAND` — voice is generated only when the player presses `🔊 Озвучить ответ`

The existing `TEAMMATE / COACH` setting remains the conversation persona. It is not a voice-cloning selector.

## Telegram UX

The existing Premium button `🎙 Голос: Тиммейт/Коуч` is intercepted by the narrow voice controller and opens a combined panel:

- TEAMMATE / COACH persona
- Voice OFF
- Voice AUTO
- Voice ON-DEMAND
- Speak last answer

No rewrite of `app/core/router.py` is required.

## Pipeline

```text
AI text answer
    ↓
working memory detects a new assistant turn
    ↓
VoiceTelegramController
    ↓
clean speech text
    ↓
Piper ONNX CPU synthesis → WAV
    ↓
bundled ffmpeg → OGG/Opus
    ↓
Telegram sendVoice
```

The text answer is always sent first and remains authoritative.

## Failure behavior

Voice is optional. A failure in any of these components must not take down the bot:

- model host unavailable
- Piper/ONNX failure
- ffmpeg conversion failure
- Telegram `sendVoice` failure

AUTO failures are logged without replacing the text response. Explicit ON-DEMAND failures show a short voice-unavailable message.

## Model lifecycle

`render.yaml` preloads the model during build with:

```text
python -m app.services.voice.prepare
```

If preload fails, build is allowed to continue. The same model manager retries lazily on the first voice request.

## Runtime configuration

```text
VOICE_ENABLED=1
VOICE_PROVIDER=piper
VOICE_MODEL_NAME=ru_RU-denis-medium
VOICE_MODEL_DIR=.bco_voice
VOICE_MODEL_TIMEOUT_S=120
VOICE_MAX_CHARS=1600
```

No TTS API key is required.

## Privacy

- generated WAV/OGG files exist only in a per-request temporary directory;
- temporary audio is deleted immediately after Telegram upload;
- voice audio is not stored in Supabase;
- the Piper model contains no user data;
- no voice cloning or imitation of a real person is implemented.

## Cost controls

- no paid TTS provider;
- model is loaded once per process and reused;
- one synthesis runs at a time per process to keep CPU/RAM predictable;
- `VOICE_MAX_CHARS` caps long spoken replies;
- default mode is OFF, so existing users do not suddenly incur TTS latency.

## Future

Possible later providers can sit behind the same `VoiceService` boundary. They must preserve:

- explicit user mode control;
- server-side secrets only;
- text-first behavior;
- no real-person voice imitation without a separate consent-safe design;
- graceful fallback when TTS is unavailable.
