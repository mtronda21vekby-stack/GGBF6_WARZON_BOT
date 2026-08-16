# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import certifi
import httpx
from openai import OpenAI

try:
    import imageio_ffmpeg
except Exception:  # pragma: no cover - tested through capability fallback
    imageio_ffmpeg = None


_TIME_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\s*$")
_SAFE_KEY_RE = re.compile(r"[^a-z0-9_]+")


class VODError(RuntimeError):
    pass


class VODCapabilityError(VODError):
    pass


@dataclass(frozen=True)
class VODRequest:
    timecodes: list[str]
    note: str = ""
    has_media: bool = False


@dataclass(frozen=True)
class VODMedia:
    file_id: str
    file_unique_id: str = ""
    kind: str = "video"
    mime_type: str = "video/mp4"
    file_size: int = 0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    file_name: str = ""


@dataclass(frozen=True)
class FrameSample:
    timestamp_s: float
    jpeg_bytes: bytes


@dataclass(frozen=True)
class VODTimelineItem:
    timestamp: str
    observation: str
    decision: str
    issue: str
    correction: str
    category: str = "decision"
    confidence: float = 0.0


@dataclass(frozen=True)
class VODMistake:
    key: str
    label: str
    category: str = "decision"
    confidence: float = 0.0


@dataclass
class VODAnalysisResult:
    summary: str
    timeline: list[VODTimelineItem] = field(default_factory=list)
    mistakes: list[VODMistake] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    next_drill: str = ""
    limitations: str = ""
    sampled_timestamps: list[str] = field(default_factory=list)
    model: str = ""

    def memory_payload(self) -> dict[str, Any]:
        return {
            "kind": "vod_sampled_frames",
            "summary": self.summary[:1200],
            "mistakes": [
                {
                    "key": x.key,
                    "label": x.label,
                    "category": x.category,
                    "confidence": x.confidence,
                }
                for x in self.mistakes[:8]
            ],
            "strengths": self.strengths[:8],
            "next_drill": self.next_drill[:800],
            "limitations": self.limitations[:800],
            "sampled_timestamps": self.sampled_timestamps[:12],
            "model": self.model,
        }


def parse_timecode(value: str) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    m = _TIME_RE.match(raw)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    millis = int((m.group(4) or "0").ljust(3, "0"))
    if minutes >= 60 or seconds >= 60:
        return None
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def format_timecode(seconds: float) -> str:
    value = max(0, int(round(float(seconds or 0))))
    h, rem = divmod(value, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _dedupe(values: Iterable[float], tolerance: float = 0.75) -> list[float]:
    out: list[float] = []
    for value in sorted(max(0.0, float(x)) for x in values):
        if not out or abs(value - out[-1]) > tolerance:
            out.append(value)
    return out


def select_sample_timestamps(
    *,
    duration_s: float,
    requested_timecodes: list[str] | None = None,
    max_frames: int = 8,
) -> list[float]:
    max_frames = max(1, min(int(max_frames or 8), 12))
    duration = max(0.0, float(duration_s or 0.0))

    requested = [
        parsed
        for parsed in (parse_timecode(x) for x in (requested_timecodes or []))
        if parsed is not None
    ]
    if duration > 0:
        requested = [min(max(0.05, x), max(0.05, duration - 0.05)) for x in requested]
    requested = _dedupe(requested)

    if duration > 0:
        anchors = [duration * x for x in (0.08, 0.22, 0.38, 0.55, 0.72, 0.88)]
        anchors = [min(max(0.05, x), max(0.05, duration - 0.05)) for x in anchors]
    else:
        anchors = [1.0, 3.0, 5.0, 8.0, 12.0, 20.0]

    picked = requested[:max_frames]
    for value in anchors:
        if len(picked) >= max_frames:
            break
        if all(abs(value - existing) > 0.75 for existing in picked):
            picked.append(value)
    return sorted(_dedupe(picked))[:max_frames]


def telegram_media_from_message(message: dict[str, Any] | None) -> VODMedia | None:
    msg = message or {}
    raw: dict[str, Any] | None = None
    kind = ""

    if isinstance(msg.get("video"), dict):
        raw = msg["video"]
        kind = "video"
    elif isinstance(msg.get("document"), dict):
        doc = msg["document"]
        mime = str(doc.get("mime_type") or "").lower()
        name = str(doc.get("file_name") or "").lower()
        if mime.startswith("video/") or name.endswith((".mp4", ".mov", ".m4v", ".webm", ".mkv")):
            raw = doc
            kind = "document"

    if not raw:
        return None
    file_id = str(raw.get("file_id") or "").strip()
    if not file_id:
        return None
    return VODMedia(
        file_id=file_id,
        file_unique_id=str(raw.get("file_unique_id") or ""),
        kind=kind,
        mime_type=str(raw.get("mime_type") or "video/mp4"),
        file_size=int(raw.get("file_size") or 0),
        duration=float(raw.get("duration") or 0.0),
        width=int(raw.get("width") or 0),
        height=int(raw.get("height") or 0),
        file_name=str(raw.get("file_name") or ""),
    )


class FrameExtractor:
    def __init__(self, *, max_frames: int = 8, max_width: int = 1280, timeout_s: float = 20.0):
        self.max_frames = max(1, min(int(max_frames or 8), 12))
        self.max_width = max(320, min(int(max_width or 1280), 1920))
        self.timeout_s = max(3.0, float(timeout_s or 20.0))

    def _ffmpeg(self) -> str:
        if imageio_ffmpeg is None:
            raise VODCapabilityError("imageio-ffmpeg is not installed")
        try:
            return str(imageio_ffmpeg.get_ffmpeg_exe())
        except Exception as exc:
            raise VODCapabilityError("ffmpeg executable is unavailable") from exc

    def probe_duration(self, video_path: str) -> float:
        if imageio_ffmpeg is None:
            return 0.0
        gen = None
        try:
            gen = imageio_ffmpeg.read_frames(video_path, pix_fmt="rgb24")
            meta = next(gen)
            return max(0.0, float(meta.get("duration") or 0.0))
        except Exception:
            return 0.0
        finally:
            if gen is not None:
                try:
                    gen.close()
                except Exception:
                    pass

    def extract(
        self,
        video_path: str,
        *,
        duration_s: float = 0.0,
        requested_timecodes: list[str] | None = None,
    ) -> list[FrameSample]:
        path = Path(video_path)
        if not path.exists() or not path.is_file():
            raise VODError("video file is missing")

        duration = max(0.0, float(duration_s or 0.0))
        if duration <= 0:
            duration = self.probe_duration(str(path))

        timestamps = select_sample_timestamps(
            duration_s=duration,
            requested_timecodes=requested_timecodes,
            max_frames=self.max_frames,
        )
        exe = self._ffmpeg()
        samples: list[FrameSample] = []

        with tempfile.TemporaryDirectory(prefix="bco_vod_frames_") as td:
            for index, timestamp in enumerate(timestamps):
                out = Path(td) / f"frame_{index:02d}.jpg"
                cmd = [
                    exe,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale=min({self.max_width}\\,iw):-2",
                    "-q:v",
                    "4",
                    "-y",
                    str(out),
                ]
                try:
                    subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        timeout=self.timeout_s,
                    )
                except (subprocess.SubprocessError, OSError):
                    continue
                try:
                    data = out.read_bytes()
                except OSError:
                    data = b""
                if data:
                    samples.append(FrameSample(timestamp_s=timestamp, jpeg_bytes=data))

        if not samples:
            raise VODCapabilityError("no video frames could be extracted")
        return samples


class VisionVODAnalyzer:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client_factory: Callable[[], Any] | None = None,
    ):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.client_factory = client_factory

    def _client(self) -> Any:
        if self.client_factory is not None:
            return self.client_factory()
        timeout = httpx.Timeout(connect=20.0, read=90.0, write=60.0, pool=90.0)
        http_client = httpx.Client(
            timeout=timeout,
            verify=certifi.where(),
            headers={"User-Agent": "BLACK-CROWN-OPS/VOD-4.0"},
        )
        base_url = str(os.getenv("OPENAI_BASE_URL") or "").strip() or None
        return OpenAI(api_key=self.api_key, base_url=base_url, http_client=http_client)

    @staticmethod
    def _safe_key(value: str, fallback: str) -> str:
        key = _SAFE_KEY_RE.sub("_", str(value or "").lower()).strip("_")
        return (key or fallback)[:64]

    def analyze(
        self,
        *,
        samples: list[FrameSample],
        profile: dict[str, Any],
        note: str = "",
    ) -> VODAnalysisResult:
        if not self.api_key:
            raise VODCapabilityError("OPENAI_API_KEY is missing")
        if not samples:
            raise VODError("no frames supplied")

        game = str(profile.get("game") or "Warzone")
        role = str(profile.get("role") or "Flex")
        input_device = str(profile.get("input") or "Controller")
        mode = str(profile.get("mode") or "")
        brain = str(profile.get("difficulty") or "Normal")

        system = (
            "You are BLACK CROWN OPS VOD Intelligence. Analyze only the sampled gameplay frames supplied. "
            "Do not claim continuous-video, audio, killfeed, minimap, enemy movement, recoil, or events between frames "
            "unless directly visible. Separate observation from inference. Return valid JSON only. "
            "The user-facing content must be in Russian. Keep tactical claims concrete and FPS-specific."
        )
        instruction = (
            f"Game={game}; mode={mode or 'unknown'}; input={input_device}; role={role}; brain={brain}. "
            f"Player note={note or 'none'}. "
            "Return JSON with keys: summary (string), timeline (array), mistakes (array), strengths (array), "
            "next_drill (string), limitations (string). "
            "timeline item keys: timestamp, observation, decision, issue, correction, category, confidence. "
            "mistake item keys: key, label, category, confidence. "
            "category must be one of positioning, decision, aim, movement, awareness, utility, unknown. "
            "confidence must be 0..1. Only add a recurring mistake when evidence is visible enough to justify it."
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
        for index, sample in enumerate(samples, start=1):
            content.append(
                {
                    "type": "text",
                    "text": f"FRAME {index} @ {format_timecode(sample.timestamp_s)}",
                }
            )
            encoded = base64.b64encode(sample.jpeg_bytes).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded}",
                        "detail": "low",
                    },
                }
            )

        client = self._client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            raise VODError(f"vision request failed: {type(exc).__name__}") from exc

        try:
            data = json.loads(raw)
        except Exception as exc:
            raise VODError("vision response was not valid JSON") from exc

        timeline: list[VODTimelineItem] = []
        for item in data.get("timeline") or []:
            if not isinstance(item, dict):
                continue
            try:
                conf = max(0.0, min(float(item.get("confidence") or 0.0), 1.0))
            except Exception:
                conf = 0.0
            timeline.append(
                VODTimelineItem(
                    timestamp=str(item.get("timestamp") or ""),
                    observation=str(item.get("observation") or "")[:700],
                    decision=str(item.get("decision") or "")[:500],
                    issue=str(item.get("issue") or "")[:500],
                    correction=str(item.get("correction") or "")[:700],
                    category=str(item.get("category") or "unknown")[:32],
                    confidence=conf,
                )
            )

        mistakes: list[VODMistake] = []
        for index, item in enumerate(data.get("mistakes") or []):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            try:
                conf = max(0.0, min(float(item.get("confidence") or 0.0), 1.0))
            except Exception:
                conf = 0.0
            mistakes.append(
                VODMistake(
                    key=self._safe_key(str(item.get("key") or ""), f"vod_issue_{index + 1}"),
                    label=label[:300],
                    category=str(item.get("category") or "unknown")[:32],
                    confidence=conf,
                )
            )

        strengths = [
            str(x).strip()[:300]
            for x in (data.get("strengths") or [])
            if str(x).strip()
        ][:8]
        sampled = [format_timecode(x.timestamp_s) for x in samples]

        return VODAnalysisResult(
            summary=str(data.get("summary") or "VOD разобран по выборочным кадрам.")[:1600],
            timeline=timeline[:12],
            mistakes=mistakes[:8],
            strengths=strengths,
            next_drill=str(data.get("next_drill") or "")[:900],
            limitations=str(data.get("limitations") or "")[:900],
            sampled_timestamps=sampled,
            model=self.model,
        )


class VODAnalysisService:
    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "gpt-4.1-mini",
        max_frames: int = 8,
        max_width: int = 1280,
        extractor: FrameExtractor | None = None,
        analyzer: VisionVODAnalyzer | None = None,
    ):
        self.extractor = extractor or FrameExtractor(max_frames=max_frames, max_width=max_width)
        self.analyzer = analyzer or VisionVODAnalyzer(api_key=api_key, model=model)
        self.model = model

    def build_analysis_prompt(self, request: VODRequest) -> str:
        times = ", ".join(x for x in request.timecodes if x) or "не указаны"
        capability = (
            "Видео приложено: используй только реально извлечённые кадры."
            if request.has_media
            else "Видео не анализировалось: работай только по таймкодам и описанию игрока."
        )
        return (
            f"{capability}\n"
            f"Таймкоды: {times}\n"
            f"Описание: {request.note or '—'}\n"
            "Для каждого эпизода: решение -> ошибка -> лучший вариант -> cue на следующий раз."
        )

    def analyze_media(
        self,
        video_path: str,
        *,
        media: VODMedia,
        profile: dict[str, Any],
        note: str = "",
        requested_timecodes: list[str] | None = None,
    ) -> VODAnalysisResult:
        samples = self.extractor.extract(
            video_path,
            duration_s=media.duration,
            requested_timecodes=requested_timecodes,
        )
        return self.analyzer.analyze(samples=samples, profile=profile, note=note)

    @staticmethod
    def format_report(result: VODAnalysisResult) -> str:
        lines = [
            "🎬 VOD INTELLIGENCE",
            "━━━━━━━━━━━━━━━━━━",
            result.summary.strip(),
        ]
        if result.timeline:
            lines.append("\nКлючевые кадры:")
            for item in result.timeline[:5]:
                cue = item.correction or item.issue or item.observation
                lines.append(f"• {item.timestamp or '—'} — {cue}")
        if result.mistakes:
            lines.append("\nПовторяющиеся риски:")
            for mistake in result.mistakes[:4]:
                lines.append(f"• {mistake.label} ({int(round(mistake.confidence * 100))}%)")
        if result.strengths:
            lines.append("\nЧто уже хорошо:")
            for strength in result.strengths[:3]:
                lines.append(f"• {strength}")
        if result.next_drill:
            lines.append(f"\nСледующая тренировка:\n{result.next_drill}")
        sampled = ", ".join(result.sampled_timestamps)
        lines.append(
            "\n⚠️ Это анализ выборочных кадров"
            + (f" ({sampled})" if sampled else "")
            + ", а не утверждение о каждом моменте видео."
        )
        if result.limitations:
            lines.append(f"Ограничение: {result.limitations}")
        return "\n".join(lines)[:3800]

    @staticmethod
    def intro_text(max_bytes: int) -> str:
        mb = max(1, int(max_bytes) // (1024 * 1024))
        return (
            "🎬 VOD Intelligence готов.\n\n"
            "Пришли gameplay-видео или MP4-документ прямо сюда. "
            f"Для стандартного Telegram Bot API — до {mb} MB.\n"
            "Можно добавить подпись: что ты хотел сделать или конкретные таймкоды.\n\n"
            "Я возьму выборочные кадры, разберу позиционку/решения/мувмент "
            "и сохраню подтверждённые ошибки в твоём Player Intelligence."
        )
