# -*- coding: utf-8 -*-
from __future__ import annotations

import json
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
_LOUDNORM_JSON_RE = re.compile(r"\{\s*\"input_i\".*?\}", re.DOTALL)

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
    (re.compile(r"\bUAV\b", re.IGNORECASE), "ю-эй-ви"),
    (re.compile(r"\bSMG\b", re.IGNORECASE), "эс-эм-джи"),
    (re.compile(r"\bLMG\b", re.IGNORECASE), "эл-эм-джи"),
    (re.compile(r"\bRPM\b", re.IGNORECASE), "ар-пи-эм"),
    (re.compile(r"\b1\s*[vV]\s*1\b"), "один на один"),
    (re.compile(r"(?<=\d)\s*%"), " процентов"),
    (re.compile(r"(?<=\d)\s*ms\b", re.IGNORECASE), " миллисекунд"),
)


def _normalize_spoken_terms(text: str) -> str:
    value = str(text or "")
    value = value.replace("→", " затем ").replace("⇒", " затем ")
    value = value.replace("&", " и ")
    value = value.replace("+", " плюс ")
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


def _truncate_on_phrase(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    for sep in ("\n\n", ". ", "! ", "? ", "; ", ", "):
        pos = cut.rfind(sep)
        if pos >= int(limit * 0.65):
            cut = cut[: pos + len(sep)].rstrip()
            break
    return cut


def clean_tts_text(text: str, max_chars: int = 2200) -> str:
    """Convert a rich Telegram answer into natural speech-ready plain text.

    Paragraph boundaries are retained because modern steerable TTS uses them as
    prosody cues. Decorative chrome, links and markdown are removed; common FPS
    abbreviations receive stable pronunciation hints.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = _CODE_BLOCK_RE.sub(" ", raw)
    raw = _URL_RE.sub(" ", raw)

    paragraphs: list[list[str]] = [[]]
    for source_line in raw.splitlines():
        original = source_line.strip()
        if not original:
            if paragraphs[-1]:
                paragraphs.append([])
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
            paragraphs[-1].append(phrase)

    rendered: list[str] = []
    for group in paragraphs:
        if not group:
            continue
        paragraph = " ".join(group)
        paragraph = re.sub(r"\s+([,.;:!?])", r"\1", paragraph)
        paragraph = _MULTI_PUNCT_RE.sub(r"\1", paragraph)
        paragraph = _MULTI_SPACE_RE.sub(" ", paragraph).strip(" .")
        if paragraph:
            rendered.append(paragraph)

    out = "\n\n".join(rendered).strip()
    if not out:
        return ""

    limit = max(160, min(int(max_chars or 2200), 4096))
    return _truncate_on_phrase(out, limit)


def _master_profile(profile: Mapping[str, Any] | None = None) -> dict[str, float]:
    data = dict(profile or {})
    persona = str(data.get("voice") or data.get("voice_mode") or "TEAMMATE").upper()
    duplex = bool(data.get("_bco_voice_reply"))

    if persona == "COACH":
        warmth_gain = 1.35
        presence_gain = 1.05
        compressor_ratio = 2.0
    else:
        warmth_gain = 0.65
        presence_gain = 1.65
        compressor_ratio = 2.25

    # Direct voice-to-voice replies get a fraction more presence so they remain
    # intelligible through phone speakers without sounding brighter in headphones.
    if duplex:
        presence_gain += 0.20

    return {
        "warmth_gain": warmth_gain,
        "presence_gain": presence_gain,
        "compressor_ratio": compressor_ratio,
        "target_i": -16.0,
        "target_lra": 5.5,
        "target_tp": -1.0,
    }


def _pre_master_filter(profile: Mapping[str, Any] | None = None) -> str:
    cfg = _master_profile(profile)
    return ",".join(
        [
            "highpass=f=58",
            "lowpass=f=14500",
            f"equalizer=f=175:t=q:w=1.15:g={cfg['warmth_gain']}",
            "equalizer=f=520:t=q:w=1.0:g=-0.45",
            f"equalizer=f=2850:t=q:w=1.05:g={cfg['presence_gain']}",
            "equalizer=f=7200:t=q:w=1.2:g=-0.35",
            (
                "acompressor="
                f"threshold=-20dB:ratio={cfg['compressor_ratio']}:"
                "attack=7:release=125:makeup=1.25:knee=2.8"
            ),
        ]
    )


def _one_pass_master_filter(profile: Mapping[str, Any] | None = None) -> str:
    cfg = _master_profile(profile)
    return ",".join(
        [
            _pre_master_filter(profile),
            f"loudnorm=I={cfg['target_i']}:LRA={cfg['target_lra']}:TP={cfg['target_tp']}",
            "alimiter=limit=0.94:attack=5:release=55:level=false",
            "apad=pad_dur=0.085",
        ]
    )


def _analyze_loudness(ffmpeg: str, source: Path, profile: Mapping[str, Any] | None = None) -> dict[str, float] | None:
    cfg = _master_profile(profile)
    analysis_filter = ",".join(
        [
            _pre_master_filter(profile),
            f"loudnorm=I={cfg['target_i']}:LRA={cfg['target_lra']}:TP={cfg['target_tp']}:print_format=json",
        ]
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(source),
        "-vn",
        "-af",
        analysis_filter,
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    matches = _LOUDNORM_JSON_RE.findall(proc.stderr or "")
    if not matches:
        return None
    try:
        payload = json.loads(matches[-1])
        result = {
            "input_i": float(payload["input_i"]),
            "input_lra": float(payload["input_lra"]),
            "input_tp": float(payload["input_tp"]),
            "input_thresh": float(payload["input_thresh"]),
            "target_offset": float(payload["target_offset"]),
        }
    except Exception:
        return None
    if not all(-120.0 < value < 120.0 for value in result.values()):
        return None
    return result


def _two_pass_master_filter(
    profile: Mapping[str, Any] | None,
    measured: Mapping[str, float],
) -> str:
    cfg = _master_profile(profile)
    loudnorm = (
        f"loudnorm=I={cfg['target_i']}:LRA={cfg['target_lra']}:TP={cfg['target_tp']}:"
        f"measured_I={measured['input_i']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=summary"
    )
    return ",".join(
        [
            _pre_master_filter(profile),
            loudnorm,
            "alimiter=limit=0.94:attack=5:release=55:level=false",
            "apad=pad_dur=0.085",
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
            "audio",
            str(target),
        ]
    )
    return command


def wav_to_ogg_opus(
    wav_path: str | Path,
    ogg_path: str | Path,
    profile: Mapping[str, Any] | None = None,
    bitrate_kbps: int = 72,
) -> Path:
    """Master lossless TTS WAV into a high-quality Telegram voice note.

    The preferred path uses measured two-pass EBU R128 normalization. If the
    bundled ffmpeg cannot provide a valid analysis, conversion falls back to a
    safe one-pass master and finally to plain Opus encoding.
    """
    source = Path(wav_path)
    target = Path(ogg_path)
    if not source.exists() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"TTS WAV not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    bitrate = max(48, min(int(bitrate_kbps or 72), 96))
    measured = _analyze_loudness(ffmpeg, source, profile)

    filters: list[str | None] = []
    if measured is not None:
        filters.append(_two_pass_master_filter(profile, measured))
    filters.extend([_one_pass_master_filter(profile), None])

    last_error = ""
    for audio_filter in filters:
        target.unlink(missing_ok=True)
        command = _ffmpeg_command(
            ffmpeg,
            source,
            target,
            bitrate_kbps=bitrate,
            audio_filter=audio_filter,
        )
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        except Exception as exc:
            last_error = type(exc).__name__
            continue
        if proc.returncode == 0 and target.exists() and target.stat().st_size > 0:
            if target.read_bytes()[:4] != b"OggS":
                target.unlink(missing_ok=True)
                last_error = "invalid Ogg container"
                continue
            return target
        last_error = (proc.stderr or "ffmpeg failed").strip()[:400]

    target.unlink(missing_ok=True)
    raise RuntimeError(f"ffmpeg voice conversion failed: {last_error}")
