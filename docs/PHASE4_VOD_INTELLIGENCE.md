# BLACK CROWN OPS — Phase 4 Real VOD Intelligence

## Goal

Upgrade the existing text/timestamp VOD workflow into real gameplay media analysis while preserving an honest capability boundary.

The system must never claim that it watched every frame of a video. Phase 4 downloads a Telegram clip, extracts a bounded set of representative JPEG frames, sends those frames to the configured OpenAI vision-capable model, and stores only evidence-backed derived intelligence.

## Runtime flow

```text
Telegram video / video document
        |
        v
VODTelegramIngress
        |
        +-- file-size gate (standard Bot API: <= 20 MB)
        |
        v
Telegram getFile + bounded streaming download
        |
        v
temporary local file
        |
        v
imageio-ffmpeg bundled ffmpeg
        |
        v
sampled JPEG frames (requested timecodes + distributed anchors)
        |
        v
OpenAI Chat Completions vision
        |
        v
structured JSON evidence
        |
        +--> user VOD report
        |
        +--> PlayerMemoryService.observe_vod()
                 |
                 +--> episode
                 +--> progression event
                 +--> recurring mistake only when confidence >= 0.65
                 +--> derived intelligence / summary refresh
```

## Privacy / retention

- Raw gameplay video is written only to a temporary directory.
- The temporary directory is deleted when the request finishes or fails.
- Raw video and JPEG frames are not stored in Supabase.
- Supabase receives only derived player intelligence and short text metadata.
- Bot token, OpenAI key, and Supabase service-role key are never logged.

## Telegram media boundary

The standard Telegram Bot API currently allows `getFile` downloads up to 20 MB. The server enforces the same default maximum with `VOD_MAX_BYTES=20971520`.

If a clip is larger, the bot asks the player to trim/compress the relevant gameplay segment. A future self-hosted Telegram Bot API server can remove this specific download limit without changing the VOD analysis architecture.

## Frame sampling

Default: up to 8 frames.

Priority:
1. user-supplied/requested timecodes when available;
2. representative anchors spread across the clip.

This is intentionally not full-frame video inference. The report explicitly states that it is based on sampled frames.

## Vision output contract

The vision model returns structured JSON:

- summary
- timeline
- mistakes
- strengths
- next_drill
- limitations

Every timeline/mistake item carries a confidence score. Only high-confidence (`>= 0.65`) mistakes are promoted into recurring player memory.

The prompt explicitly forbids inventing:
- audio cues;
- unseen enemy movement;
- killfeed/minimap details not visible;
- recoil/aim behavior between sampled frames;
- continuous-video events between snapshots.

## Environment

```text
VOD_ENABLED=1
VOD_MAX_BYTES=20971520
VOD_MAX_FRAMES=8
VOD_FRAME_WIDTH=1280
VOD_DOWNLOAD_TIMEOUT_S=60
VOD_VISION_MODEL=<optional override>
```

`VOD_VISION_MODEL` defaults to `OPENAI_MODEL`.

## Dependencies

Phase 4 adds:

```text
imageio-ffmpeg==0.6.0
```

The Linux wheel includes an ffmpeg executable used through `imageio_ffmpeg.get_ffmpeg_exe()`, avoiding a dependency on a separately installed system ffmpeg.

## Failure behavior

Failures are fail-safe:

- oversized Telegram file -> no download;
- download error -> no analysis;
- ffmpeg unavailable -> text/timestamp VOD remains available;
- vision failure -> no fabricated report;
- memory write failure -> user still receives the completed VOD report;
- temporary files are deleted.

## Production validation

Automated tests must not call Telegram or OpenAI over the network.

Tests cover:
- timecode parsing;
- sample selection;
- Telegram video/document detection;
- actual frame extraction using bundled ffmpeg;
- structured vision parsing with a fake client;
- bounded Telegram file download with `httpx.MockTransport`;
- high-confidence VOD findings entering player memory;
- FastAPI import smoke.
