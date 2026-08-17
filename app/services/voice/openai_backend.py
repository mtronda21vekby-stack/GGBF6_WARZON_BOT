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
DEFAULT_TTS_VOICE = "marin"
ALLOWED_TTS_VOICES = frozenset({"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar"})


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


def _locale(profile: Mapping[str, Any]) -> str:
    raw = _profile_value(profile, "language", "locale", "language_code", fallback="ru").casefold()
    return "en" if raw.startswith("en") else "ru"


def _content_direction(text: str) -> str:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return ""
    if len(clean) <= 220:
        return "Deliver it as one natural short spoken reply, not as a read-out script."
    if len(clean) >= 1100:
        return "For the longer answer, use natural conversational paragraph breaks and reset the breath only when the idea changes."
    return "Keep a natural conversational arc and let the actionable ending land clearly."


def _voice_character(profile: Mapping[str, Any]) -> str:
    identity = str(profile.get("voice_identity") or "").strip().casefold()
    if identity == "female":
        return "Use an adult original female tactical-intelligence delivery: precise, calm, controlled, premium, authoritative without shouting; never childish, seductive, cartoonish or imitative of a real person."
    if identity == "male":
        return "Use an adult original male tactical-intelligence delivery: grounded, composed, natural and highly intelligible; no trailer voice, growl or artificial bass exaggeration."
    voice = normalize_tts_voice(profile.get("tts_voice"))
    if voice == "marin": return "Use a warm, modern, soft and confident synthetic delivery with light expressive color and no artificial sweetness."
    if voice == "coral": return "Use a warm, friendly and grounded synthetic delivery with relaxed energy and clean articulation."
    if voice == "shimmer": return "Use a lighter, clear and lively synthetic delivery; keep it mature, calm and never cartoonish."
    if voice == "nova": return "Use a clean, bright and conversational synthetic delivery with restrained energy."
    if voice == "cedar": return "Use a lower, composed tactical synthetic delivery with natural speech rhythm and no announcer effect."
    return "Use the selected synthetic voice naturally and conversationally."


def voice_instructions(profile: Mapping[str, Any] | None, text: str = "") -> str:
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="NORMAL").upper()
    emotion = _profile_value(data, "emotion", "emotional_state", fallback="CALM").upper()
    locale = _locale(data)
    language_rules = (["Speak fluent natural English to one person in a close conversational voice.", "Keep FPS product, weapon, map, mode and esports terms in their canonical English form."] if locale == "en" else ["Speak fluent natural Russian to one person in a close conversational voice.", "Keep English FPS terms natural inside Russian speech. Do not translate weapon, map, mode or product names."])
    instructions = language_rules + [
        "Sound human and spontaneous, not like a narrator, announcer, audiobook, call center, movie trailer, radio operator or generic AI assistant.",
        "Do not imitate or reference any real person. This is an original synthetic BLACK CROWN voice identity.",
        "Use relaxed connected speech, natural micro-pauses and uneven emphasis; do not over-enunciate every word or stress every sentence equally.",
        "Avoid a repetitive falling cadence at the end of every sentence; group related phrases into one natural thought and breathe when the idea changes.",
        "Do not read markdown, emoji, URLs, separators, UI labels or BLACK CROWN headers aloud.",
        "Preserve negations, numbers and tactical meaning exactly.", _voice_character(data)]
    if bool(data.get("_bco_voice_reply")):
        instructions.append("This directly answers the player's voice message: enter the answer immediately, keep it conversational, and avoid an intro or recap of the question.")
    instructions.append("As COACH, be calm, analytical and emphasize the root cause and next correction." if persona == "COACH" else "As TEAMMATE, be concise, fast and natural like a strong squadmate between fights, not military roleplay.")
    if brain == "DEMON": instructions.append("For DEMON mode, lower the emotional temperature and be more decisive and information-dense, but never shout, growl or perform a villain persona.")
    elif brain == "PRO": instructions.append("For PRO mode, keep confident professional precision and higher information density without sounding formal.")
    if emotion in {"TILT", "ANGRY", "ANXIOUS"}: instructions.append("Lower the energy slightly and make the key correction easy to hear; do not make psychological claims.")
    elif emotion in {"HYPE", "EXCITED"}: instructions.append("Allow a little extra energy while keeping delivery controlled and natural.")
    content = _content_direction(text)
    if content: instructions.append(content)
    return " ".join(instructions)


def voice_speed(profile: Mapping[str, Any] | None) -> float:
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    emotion = _profile_value(data, "emotion", "emotional_state", fallback="CALM").upper()
    speed = 0.975 if persona == "COACH" else 1.0
    if bool(data.get("_bco_voice_reply")): speed += 0.005
    if emotion in {"TILT", "ANGRY", "ANXIOUS"}: speed -= 0.02
    elif emotion in {"HYPE", "EXCITED"}: speed += 0.005
    return max(0.94, min(speed, 1.025))


class OpenAITTSBackend:
    def __init__(self, *, api_key: str, model: str = DEFAULT_TTS_MODEL, default_voice: str = DEFAULT_TTS_VOICE, timeout_s: float = 45.0, max_bytes: int = 20 * 1024 * 1024, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = str(api_key or "").strip(); self.model = str(model or DEFAULT_TTS_MODEL).strip()[:120]; self.default_voice = normalize_tts_voice(default_voice); self.max_bytes = max(256 * 1024, min(int(max_bytes or 0), 64 * 1024 * 1024)); timeout = max(5.0, min(float(timeout_s or 45.0), 120.0)); self._owns_client = client is None; self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(connect=min(timeout, 20.0), read=timeout, write=timeout, pool=timeout))
    @property
    def configured(self) -> bool: return bool(self._api_key and self.model)
    def voice_for(self, profile: Mapping[str, Any] | None) -> str:
        data = dict(profile or {}); explicit = str(data.get("tts_voice") or "").strip(); return normalize_tts_voice(explicit, self.default_voice) if explicit else self.default_voice
    async def close(self) -> None:
        if self._owns_client: await self._client.aclose()
    async def _download_once(self, *, text: str, output: Path, profile: Mapping[str, Any]) -> Path:
        if not self.configured: raise RuntimeError("OpenAI TTS is not configured")
        payload = {"model": self.model, "voice": self.voice_for(profile), "input": str(text or "")[:4096], "instructions": voice_instructions(profile, text)[:4096], "response_format": "wav", "stream_format": "audio", "speed": voice_speed(profile)}
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json", "Accept": "audio/wav, application/octet-stream", "User-Agent": "BLACK-CROWN-OPS/voice-intelligence-v38", "X-Client-Request-Id": str(uuid.uuid4())}
        output.parent.mkdir(parents=True, exist_ok=True); part = output.with_suffix(output.suffix + ".part"); part.unlink(missing_ok=True); total = 0
        try:
            async with self._client.stream("POST", OPENAI_SPEECH_URL, headers=headers, json=payload) as response:
                response.raise_for_status(); declared = int(response.headers.get("content-length") or 0)
                if declared and declared > self.max_bytes: raise RuntimeError("OpenAI TTS audio exceeded configured size limit")
                with part.open("wb") as file_handle:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        if not chunk: continue
                        total += len(chunk)
                        if total > self.max_bytes: raise RuntimeError("OpenAI TTS audio exceeded configured size limit")
                        file_handle.write(chunk)
            if total < 44: raise RuntimeError("OpenAI TTS returned empty audio")
            with part.open("rb") as file_handle: header = file_handle.read(12)
            if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE": raise RuntimeError("OpenAI TTS returned an invalid WAV payload")
            part.replace(output); return output
        except Exception:
            part.unlink(missing_ok=True); raise
    async def synthesize_wav(self, text: str, output_path: str | Path, profile: Mapping[str, Any] | None = None) -> Path:
        output = Path(output_path); data = dict(profile or {}); last_error: Exception | None = None
        for attempt in range(2):
            try: return await self._download_once(text=text, output=output, profile=data)
            except httpx.HTTPStatusError as exc:
                last_error = exc; status = int(exc.response.status_code)
                if attempt == 0 and (status == 429 or status >= 500): await asyncio.sleep(0.35); continue
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == 0: await asyncio.sleep(0.35); continue
                raise
        raise RuntimeError("OpenAI TTS failed") from last_error
