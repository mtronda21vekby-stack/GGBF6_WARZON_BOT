# BLACK CROWN OPS v21 — Voice Studio

## Objective

Make Telegram voice a dependable first-class input and make voice-to-voice replies sound like an ongoing conversation rather than a written answer being read aloud.

## Production defect fixed

The v20 STT client constructed multipart form fields as a list of tuples while also attaching a file. Current `httpx` multipart encoding expects mapping-like form data in this path. The resulting client-side exception could occur before an HTTP request reached OpenAI and surfaced in Telegram as the generic `voice input unavailable` message.

v21 constructs bounded multipart fields as a dictionary and wraps unexpected transport/encoding exceptions inside the transcription boundary.

A real `httpx.MockTransport` regression test now exercises the multipart encoder end-to-end. CI therefore fails if the actual HTTP request cannot be constructed.

## Input formats

Telegram native voice notes remain OGG/Opus. Generic Telegram audio attachments now preserve an appropriate temporary file suffix rather than forcing every attachment to `.ogg`.

Supported temporary formats include:

- OGG / Opus;
- MP3;
- M4A / MP4 audio;
- WAV;
- WebM;
- FLAC.

The transcription upload derives its MIME type from the actual temporary file.

## Speech recognition

Primary:

```text
gpt-4o-transcribe
```

Fallback:

```text
gpt-4o-mini-transcribe
```

Russian remains the language hint while the bounded FPS vocabulary prompt preserves common English competitive-game terminology.

Low-confidence transcripts are still stopped before AI/memory and require explicit user confirmation.

Audio remains ephemeral and is deleted with the temporary directory after transcription.

## Voice-to-voice delivery

Smart Duplex now marks generated speech as a direct reply to voice input. The TTS director receives transient, non-persistent context telling it to:

- continue the live conversation immediately;
- avoid sounding like it is reading the written answer;
- use a quicker first sentence and connected Russian phrasing;
- keep the spoken version dense while the full authoritative response stays visible in Telegram.

Voice-to-voice speech has its own bounded character budget:

```text
VOICE_DUPLEX_MAX_CHARS=1400
```

Manual `/speak` and regular AUTO voice can still use the larger `VOICE_MAX_CHARS` budget.

No second LLM summarization call is introduced.

## Existing quality preserved

- Cedar / Marin selection;
- TEAMMATE / COACH delivery;
- Normal / Pro / Demon cadence;
- emotion-aware delivery without changing factual conclusions;
- WAV generation and mastering;
- 64 kbit/s Telegram Opus;
- local Piper fallback;
- text remains authoritative if voice output fails.

## Validation

v21 adds tests that prove:

1. real multipart STT encoding reaches the HTTP transport;
2. language, model, logprob request and filename are actually encoded;
3. compatible 400 responses retry without logprobs;
4. voice-to-voice direction differs from ordinary read-aloud TTS;
5. duplex replies use a smaller spoken budget while retaining the full text answer.

Release target:

```text
21.0.0 / bco-voice-studio-v21
```
