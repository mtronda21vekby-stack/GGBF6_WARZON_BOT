# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path

import imageio_ffmpeg

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MARKDOWN_RE = re.compile(r"[*_`#>|]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


def clean_tts_text(text: str, max_chars: int = 1600) -> str:
    """Convert a rich Telegram answer into speech-friendly plain text.

    The function intentionally removes BLACK CROWN decorative chrome, URLs,
    emoji/symbol glyphs and markdown, while preserving Russian/English words,
    numbers and useful punctuation.
    """
    raw = str(text or "").replace("\r", "\n")
    raw = _URL_RE.sub("", raw)
    lines: list[str] = []
    for source_line in raw.splitlines():
        line = source_line.strip()
        if not line:
            continue
        upper = line.upper()
        if "BLACK CROWN OPS" in upper or upper in {"— BCO", "- BCO"}:
            continue
        if set(line) <= {"━", "─", "-", "_", "="}:
            continue
        line = line.lstrip("•·-— ").strip()
        if not line:
            continue
        filtered = []
        for ch in line:
            cat = unicodedata.category(ch)
            if cat in {"So", "Cs"}:
                continue
            filtered.append(ch)
        line = _MARKDOWN_RE.sub("", "".join(filtered)).strip()
        if line:
            lines.append(line)

    out = ". ".join(lines)
    out = _MULTI_SPACE_RE.sub(" ", out).strip(" .")
    if not out:
        return ""

    limit = max(120, int(max_chars or 1600))
    if len(out) <= limit:
        return out

    cut = out[:limit].rstrip()
    for sep in (". ", "! ", "? ", "; ", ", "):
        pos = cut.rfind(sep)
        if pos >= int(limit * 0.65):
            cut = cut[: pos + 1].rstrip()
            break
    return cut


def wav_to_ogg_opus(wav_path: str | Path, ogg_path: str | Path) -> Path:
    source = Path(wav_path)
    target = Path(ogg_path)
    if not source.exists() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"TTS WAV not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", str(source),
        "-vn",
        "-ac", "1",
        "-ar", "48000",
        "-c:a", "libopus",
        "-b:a", "32k",
        "-application", "voip",
        str(target),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg voice conversion failed: {(proc.stderr or '').strip()[:400]}")
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("ffmpeg produced an empty Telegram voice file")
    return target
