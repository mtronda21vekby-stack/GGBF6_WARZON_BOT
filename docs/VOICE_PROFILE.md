# Shared CROWN voice profile

BLACK CROWN has one server-owned voice configuration. Telegram, Web and native iOS are transport adapters around `app.services.voice.VoiceService`; they do not own separate provider credentials or personality settings.

## Canonical profile

Public profile ID: `black-crown-canonical-v1`

Safe metadata exposed to an authenticated native client includes supported locale capabilities, conversational presentation, quality/fallback availability, buffered PCM transport, AudioClock timing authority and codec support. Provider secrets and privileged provider identifiers are never returned.

The existing production configuration selects the existing OpenAI high-fidelity TTS backend when its Render secret is configured. The existing local Piper model is the Russian degraded fallback. Piper is not presented as English-capable.

## Surface adapters

- Telegram/Web keep their established OGG/Opus mastering and delivery paths.
- iOS requests bounded spoken segments and receives `pcm_s16le` chunks through `crown-voice-v1`.
- iOS converts PCM to the existing `SpeechAudioChunk` abstraction. `CrownAudioPlaybackEngine` and actual `CrownAudioClock` remain authoritative for Speaking state.
- Apple system speech remains an explicit device fallback when authenticated server synthesis fails before emitting audio.

## Cancellation

Native requests carry server-authorized identity plus session, turn, speech generation, request and segment identifiers. Barge-in closes local synthesis consumption, calls the authenticated server cancel route, flushes playback, invalidates the AudioClock generation, and rejects late chunks. A completed `request_id` cannot synthesize twice in one server process.

## Current limitation

The existing provider returns a completed WAV artifact. The native API then streams bounded PCM chunks, so transport is incremental but first audio waits for one spoken segment to synthesize. Future provider-native audio streaming can replace this adapter without changing CrownVoice or the protocol ownership model.
