# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Mapping

import imageio_ffmpeg

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_MARKDOWN_RE = re.compile(r"[*_`#>|]+")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_PUNCT_RE = re.compile(r"([.!?])\1+")

_SPOKEN_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bK\s*/\s*D\b", re.IGNORECASE), "кей-ди"),
    (re.compile(r"\bKD\b", re.IGNORECASE), "кей-ди"),
    (re.compile(r"\bTTK\b", re.IGNORECASE), "ти-ти-кей"),
    (re.compile(r"\bADS\b", re.IGNORECASE), "эй-ди-эс"),
    (re.compile(r"\bFOV\b", re.IGNORECASE), "эф-о-ви"),
    (re.compile(r"\bFPS\b", re.IGNORECASE), "эф-пи-эс"),
    (re.compile(r"\bVOD\b", re.IGNORECASE), "вод"),
    (re.compile(r"\bAI\b", re.IGNORECASE), "эй-ай"),
    (re.compile(r"\bKBM\b", re.IGNORECASE), "кей-би-эм"),
    (re.compile(r"\b1\s*[vV]\s*1\b"), "один на один"),
    (re.compile(r"(?<=\d)\s*%"), " процентов"),
    (re.compile(r"(?<=\d)\s*ms\b", re.IGNORECASE), " миллисекунд"),
)


def _normalize_spoken_terms(text: str) -> str:
    value = str(text or "")
    value = value.replace("→", " затем ").replace("⇒", " затем ")
    value = value.replace("&", " и ")
    for pattern, replacement in _SPOKEN_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    return value


def _remove_symbol_glyphs(text: str) -> str:
    filtered: list[str] = []
    for ch in str(text or ""):
        category = unicodedata.category(ch)
        if category in {"So", "Cs", "Co"}:
            continue
        filtered.append(ch)
    return "".join(filtered)


def _finish_phrase(line: str, *, heading: bool = False) -> str:
    value = line.strip()
    if not value:
        return ""
    if heading and not value.endswith(":"):
        return value.rstrip(".;,!? ") + ":"
    if value.endswith((".", "!", "?", ":", ";")):
        return value
    return value.rstrip(", ") + "."


def clean_tts_text(text: str, max_chars: int = 1600) -> str:
    """Convert a rich Telegram answer into natural speech-ready plain text.

    Decorative chrome and unsafe markup are removed, common FPS abbreviations
    receive explicit Russian pronunciation, and original sentence punctuation
    is preserved instead of forcing an artificial period after every line.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = _CODE_BLOCK_RE.sub(" ", raw)
    raw = _URL_RE.sub(" ", raw)

    phrases: list[str] = []
    for source_line in raw.splitlines():
        original = source_line.strip()
        if not original:
            continue
        upper = original.upper()
        if "BLACK CROWN OPS" in upper or upper in {"— BCO", "- BCO"}:
            continue
        if set(original) <= {"━", "─", "-", "_", "=", " "}:
            continue

        is_bullet = original.startswith(("•", "·", "- ", "— "))
        line = original.lstrip("•·-— ").strip()
        if not line:
            continue
        line = _remove_symbol_glyphs(line)
        line = _MARKDOWN_RE.sub("", line)
        line = _normalize_spoken_terms(line)
        line = _MULTI_SPACE_RE.sub(" ", line).strip()
        if not line:
            continue

        heading = line.endswith(":") or (
            len(line) <= 42
            and any(ch.isalpha() for ch in line)
            and line.upper() == line
            and not is_bullet
        )
        phrase = _finish_phrase(line, heading=heading)
        if phrase:
            phrases.append(phrase)

    out = " ".join(phrases)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = _MULTI_PUNCT_RE.sub(r"\1", out)
    out = _MULTI_SPACE_RE.sub(" ", out).strip(" .")
    if not out:
        return ""

    limit = max(120, min(int(max_chars or 1600), 4096))
    if len(out) <= limit:
        return out

    cut = out[:limit].rstrip()
    for sep in (". ", "! ", "? ", "; ", ", "):
        pos = cut.rfind(sep)
        if pos >= int(limit * 0.65):
            cut = cut[: pos + 1].rstrip()
            break
    return cut


def _mastering_filter(profile: Mapping[str, Any] | None = None) -> str:
    data = dict(profile or {})
    persona = str(data.get("voice") or data.get("voice_mode") or "TEAMMATE").upper()
    if persona == "COACH":
        warmth_gain = 1.2
        presence_gain = 1.0
    else:
        warmth_gain = 0.6
        presence_gain = 1.8

    return ",".join(
        [
            "highpass=f=65",
            "lowpass=f=11800",
            f"equalizer=f=180:t=q:w=1.2:g={warmth_gain}",
            f"equalizer=f=2800:t=q:w=1.1:g={presence_gain}",
            "acompressor=threshold=-21dB:ratio=2.2:attack=8:release=140:makeup=1.4:knee=2.5",
            "loudnorm=I=-18:LRA=7:TP=-1.5",
            "apad=pad_dur=0.06",
        ]
    )


def _ffmpeg_command(
    ffmpeg: str,
    source: Path,
    target: Path,
    *,
    bitrate_kbps: int,
    audio_filter: str | None,
) -> list[str]:
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
    ]
    if audio_filter:
        command.extend(["-af", audio_filter])
    command.extend(
        [
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "libopus",
            "-b:a",
            f"{bitrate_kbps}k",
            "-vbr",
            "on",
            "-compression_level",
            "10",
            "-frame_duration",
            "20",
            "-application",
            "voip",
            str(target),
        ]
    )
    return command


def wav_to_ogg_opus(
    wav_path: str | Path,
    ogg_path: str | Path,
    profile: Mapping[str, Any] | None = None,
    bitrate_kbps: int = 48,
) -> Path:
    source = Path(wav_path)
    target = Path(ogg_path)
    if not source.exists() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"TTS WAV not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    bitrate = max(32, min(int(bitrate_kbps or 48), 96))
    attempts = (
        _ffmpeg_command(
            ffmpeg,
            source,
            target,
            bitrate_kbps=bitrate,
            audio_filter=_mastering_filter(profile),
        ),
        _ffmpeg_command(
            ffmpeg,
            source,
            target,
            bitrate_kbps=bitrate,
            audio_filter=None,
        ),
    )

    last_error = ""
    for command in attempts:
        target.unlink(missing_ok=True)
        proc = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode == 0 and target.exists() and target.stat().st_size > 0:
            if target.read_bytes()[:4] != b"OggS":
                target.unlink(missing_ok=True)
                last_error = "invalid Ogg container"
                continue
            return target
        last_error = (proc.stderr or "ffmpeg failed").strip()[:400]

    target.unlink(missing_ok=True)
    raise RuntimeError(f"ffmpeg voice conversion failed: {last_error}")
