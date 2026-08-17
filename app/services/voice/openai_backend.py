# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Mapping

import httpx

log = logging.getLogger("bco.voice.openai")

OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "cedar"
ALLOWED_TTS_VOICES = frozenset(
    {
        "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx",
        "sage", "shimmer", "verse", "marin", "cedar",
    }
)


def normalize_tts_voice(value: Any, fallback: str = DEFAULT_TTS_VOICE) -> str:
    requested = str(value or "").strip().casefold()
    if requested in ALLOWED_TTS_VOICES:
        return requested
    normalized_fallback = str(fallback or DEFAULT_TTS_VOICE).strip().casefold()
    return normalized_fallback if normalized_fallback in ALLOWED_TTS_VOICES else DEFAULT_TTS_VOICE


def _profile_value(profile: Mapping[str, Any], *keys: str, fallback: str = "") -> str:
    for key in keys:
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    return fallback


def _content_direction(text: str) -> str:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return ""
    clauses = clean.count(".") + clean.count("!") + clean.count("?") + clean.count(";")
    if len(clean) <= 220 and clauses <= 3:
        return (
            "Treat this as a short tactical callout. Enter immediately, keep one compact breath arc, "
            "and land the final action with a clean low ending."
        )
    if len(clean) >= 1200:
        return (
            "Treat this as a longer coaching debrief. Group meaning into audible paragraphs, slightly reset the breath between "
            "cause, correction and next action, and keep the final third as controlled as the opening."
        )
    if any(marker in clean for marker in ("Перв", "Втор", "1.", "2.", "•")):
        return (
            "The answer contains priorities. Separate each priority with a short natural pause and a small change in emphasis, "
            "but never sound like a list-reading accessibility voice."
        )
    return "Use one natural conversational arc: context, decisive insight, then the actionable ending."


def voice_instructions(profile: Mapping[str, Any] | None, text: str = "") -> str:
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="NORMAL").upper()
    emotion = _profile_value(data, "emotion", "emotional_state", fallback="CALM").upper()
    duplex_reply = bool(data.get("_bco_voice_reply"))

    instructions = [
        "Speak fluent natural Russian in a close-mic premium studio style with a neutral native Russian accent.",
        "The voice is synthetic: do not imitate, reference, or resemble any real named person.",
        "Sound like a highly experienced competitive-FPS operator speaking to one player, not like a generic assistant.",
        "Keep the signal dry and intimate: no announcer voice, movie trailer voice, radio distortion, reverb, whisper effect, or theatrical growl.",
        "Use human breath groups, micro-pauses, variable sentence length, clean consonants and relaxed connected speech.",
        "Avoid the synthetic assistant cadence where every phrase receives equal stress or every sentence rises at the end.",
        "Give at most one strong emphasis per thought. Let secondary information stay quieter and faster.",
        "Pronounce Russian naturally and English gaming terms confidently inside Russian speech without caricaturing an English accent.",
        "Preserve weapon names, map names, negations, quantities and tactical abbreviations exactly in meaning.",
        "Do not read markdown, emoji, separators, URLs, UI chrome, bullet symbols, or the BLACK CROWN brand header aloud.",
        "Never add filler, greetings, laughter, sighs, sound effects or a sign-off that is not present in the text.",
        "Finish instructions with a calm decisive downward cadence rather than exaggerated emphasis.",
    ]

    if duplex_reply:
        instructions.extend([
            "This is a direct reply to a voice message. Continue the conversation immediately as if the player is still in comms.",
            "The first sentence should arrive quickly and naturally; do not introduce or summarize the fact that you are answering.",
            "Use fewer formal pauses, smoother connected phrasing and a compact spoken form while the complete written answer remains visible.",
        ])

    if persona == "COACH":
        instructions.extend([
            "Use a measured one-on-one elite esports coach manner: calm authority, slightly warmer tone, controlled pacing.",
            "Pause briefly before the root cause, the correction and the measurable next action.",
            "Criticism is precise and emotionally neutral; encouragement is brief and earned.",
        ])
    else:
        instructions.extend([
            "Use the manner of a trusted high-level squad teammate on clean comms: brisk, direct, composed and easy to process under pressure.",
            "Short tactical sentences may connect tightly; strategic explanations may breathe slightly more.",
        ])

    if brain == "DEMON":
        instructions.append(
            "Add restrained intensity through firmer consonants and endings, without shouting, theatrical pitch lowering, or roleplay."
        )
    elif brain == "PRO":
        instructions.append("Use precise professional emphasis and a focused tournament-review cadence.")
    else:
        instructions.append("Keep the delivery relaxed, transparent and immediately understandable on first listen.")

    if emotion in {"TILT", "ANGRY", "ANXIOUS"}:
        instructions.append(
            "Lower emotional intensity because the player may be overloaded: reduce vocal energy, widen the most important pause slightly, and make the correction exceptionally clear."
        )
    elif emotion in {"HYPE", "EXCITED"}:
        instructions.append("Allow modest extra energy and faster transitions while preserving diction and control.")

    content = _content_direction(text)
    if content:
        instructions.append(content)
    return " ".join(instructions)


def voice_speed(profile: Mapping[str, Any] | None) -> float:
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="NORMAL").upper()
    emotion = _profile_value(data, "emotion", "emotional_state", fallback="CALM").upper()

    speed = 0.98 if persona == "COACH" else 1.04
    if bool(data.get("_bco_voice_reply")):
        speed += 0.015
    if brain == "DEMON":
        speed += 0.005
    if emotion in {"TILT", "ANGRY", "ANXIOUS"}:
        speed -= 0.025
    elif emotion in {"HYPE", "EXCITED"}:
        speed += 0.01
    return max(0.90, min(speed, 1.08))


class OpenAITTSBackend:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_TTS_MODEL,
        default_voice: str = DEFAULT_TTS_VOICE,
        timeout_s: float = 45.0,
        max_bytes: int = 20 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self.model = str(model or DEFAULT_TTS_MODEL).strip()[:120]
        self.default_voice = normalize_tts_voice(default_voice)
        self.max_bytes = max(256 * 1024, min(int(max_bytes or 0), 64 * 1024 * 1024))
        timeout = max(5.0, min(float(timeout_s or 45.0), 120.0))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=min(timeout, 20.0), read=timeout, write=timeout, pool=timeout)
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self.model)

    def voice_for(self, profile: Mapping[str, Any] | None) -> str:
        data = dict(profile or {})
        explicit = str(data.get("tts_voice") or "").strip()
        if explicit:
            return normalize_tts_voice(explicit, self.default_voice)
        persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
        return "marin" if persona == "COACH" else self.default_voice

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _download_once(self, *, text: str, output: Path, profile: Mapping[str, Any]) -> Path:
        if not self.configured:
            raise RuntimeError("OpenAI TTS is not configured")
        payload = {
            "model": self.model,
            "voice": self.voice_for(profile),
            "input": str(text or "")[:4096],
            "instructions": voice_instructions(profile, text)[:4096],
            "response_format": "wav",
            "stream_format": "audio",
            "speed": voice_speed(profile),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav, application/octet-stream",
            "User-Agent": "BLACK-CROWN-OPS/voice-studio-v22",
            "X-Client-Request-Id": str(uuid.uuid4()),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        part = output.with_suffix(output.suffix + ".part")
        part.unlink(missing_ok=True)
        total = 0
        try:
            async with self._client.stream("POST", OPENAI_SPEECH_URL, headers=headers, json=payload) as response:
                response.raise_for_status()
                declared = int(response.headers.get("content-length") or 0)
                if declared and declared > self.max_bytes:
                    raise RuntimeError("OpenAI TTS audio exceeded configured size limit")
                with part.open("wb") as file_handle:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > self.max_bytes:
                            raise RuntimeError("OpenAI TTS audio exceeded configured size limit")
                        file_handle.write(chunk)
            if total < 44:
                raise RuntimeError("OpenAI TTS returned empty audio")
            with part.open("rb") as file_handle:
                header = file_handle.read(12)
            if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                raise RuntimeError("OpenAI TTS returned an invalid WAV payload")
            part.replace(output)
            return output
        except Exception:
            part.unlink(missing_ok=True)
            raise

    async def synthesize_wav(self, text: str, output_path: str | Path, profile: Mapping[str, Any] | None = None) -> Path:
        output = Path(output_path)
        data = dict(profile or {})
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                return await self._download_once(text=text, output=output, profile=data)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = int(exc.response.status_code)
                if attempt == 0 and (status == 429 or status >= 500):
                    await asyncio.sleep(0.35)
                    continue
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.35)
                    continue
                raise
        raise RuntimeError("OpenAI TTS failed") from last_error
