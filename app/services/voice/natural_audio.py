# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


def wav_to_natural_ogg_opus(
    wav_path: str | Path,
    ogg_path: str | Path,
    *,
    bitrate_kbps: int = 72,
) -> Path:
    """Encode steerable cloud TTS with deliberately transparent processing.

    Neural TTS is already voiced and mastered upstream. BLACK CROWN therefore
    applies only a sub-bass safety cut, transparent peak limiting and one Opus
    encode. `application=audio` preserves timbre better than speech-optimized
    VOIP mode while remaining a Telegram-compatible mono Ogg/Opus voice note.
    """
    source = Path(wav_path)
    target = Path(ogg_path)
    if not source.exists() or source.stat().st_size <= 44:
        raise FileNotFoundError(f"Cloud TTS WAV not found: {source}")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    bitrate = max(48, min(int(bitrate_kbps or 72), 96))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    audio_filter = "highpass=f=42,alimiter=limit=0.975:attack=4:release=70:level=false,apad=pad_dur=0.075"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-map_metadata",
        "-1",
        "-af",
        audio_filter,
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "libopus",
        "-b:a",
        f"{bitrate}k",
        "-vbr",
        "on",
        "-compression_level",
        "10",
        "-frame_duration",
        "20",
        "-application",
        "audio",
        str(target),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode != 0 or not target.exists() or target.stat().st_size <= 0:
        target.unlink(missing_ok=True)
        detail = (proc.stderr or "ffmpeg failed").strip()[:400]
        raise RuntimeError(f"natural voice conversion failed: {detail}")
    if target.read_bytes()[:4] != b"OggS":
        target.unlink(missing_ok=True)
        raise RuntimeError("natural voice conversion produced invalid Ogg")
    return target
