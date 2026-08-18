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
ALLOWED_VOICE_IDENTITIES = frozenset({"female", "male"})
IDENTITY_DEFAULT_VOICES = {"female": "marin", "male": "cedar"}


def normalize_tts_voice(value: Any, fallback: str = DEFAULT_TTS_VOICE) -> str:
    requested = str(value or "").strip().casefold()
    if requested in ALLOWED_TTS_VOICES:
        return requested
    normalized_fallback = str(fallback or DEFAULT_TTS_VOICE).strip().casefold()
    return normalized_fallback if normalized_fallback in ALLOWED_TTS_VOICES else DEFAULT_TTS_VOICE


def normalize_voice_identity(value: Any) -> str:
    requested = str(value or "").strip().casefold()
    return requested if requested in ALLOWED_VOICE_IDENTITIES else ""


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
    identity = normalize_voice_identity(profile.get("voice_identity"))
    if identity == "female":
        return "Use an adult original female tactical-intelligence voice: mature, calm, natural and quietly confident; never childish, seductive or theatrical."
    if identity == "male":
        return "Use an adult original male tactical-intelligence voice: grounded, calm, natural and quietly confident; no trailer voice, growl or artificial bass performance."
    voice = normalize_tts_voice(profile.get("tts_voice"))
    if voice == "marin":
        return "Keep MARIN warm, modern and conversational."
    if voice == "coral":
        return "Keep CORAL warm, relaxed and conversational."
    if voice == "shimmer":
        return "Keep SHIMMER light, mature and conversational."
    if voice == "nova":
        return "Keep NOVA clean, natural and conversational."
    if voice == "cedar":
        return "Keep CEDAR grounded, natural and conversational."
    return "Use the selected synthetic voice in a natural conversational register."


def voice_instructions(profile: Mapping[str, Any] | None, text: str = "") -> str:
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="NORMAL").upper()
    emotion = _profile_value(data, "emotion", "emotional_state", fallback="CALM").upper()
    locale = _locale(data)

    if locale == "en":
        language = "Speak fluent natural English to one person. Keep canonical FPS, weapon, map, mode and esports terms unchanged."
    else:
        language = "Speak fluent natural Russian to one person. Keep common English FPS, weapon, map and mode names natural inside Russian speech."

    instructions = [
        language,
        _voice_character(data),
        "Use spontaneous close conversation: sound human and natural, not like a narrator, announcer, audiobook, call center, movie trailer, radio operator or generic AI assistant.",
        "Do not imitate or reference any real person.",
        "Use relaxed connected speech, subtle uneven emphasis and short natural pauses only where the thought changes. Do not over-enunciate every word or fall into a repetitive falling cadence.",
        "Do not read markdown, emoji, URLs, separators or interface labels aloud. Preserve numbers, negations and tactical meaning exactly.",
    ]

    if bool(data.get("_bco_voice_reply")):
        instructions.append("This directly answers the player's voice message: enter the answer immediately and avoid an intro or recap of the question.")

    if persona == "COACH":
        instructions.append("As COACH, stay calm and analytical; make the root cause and next correction easy to hear without sounding formal.")
    else:
        instructions.append("As TEAMMATE, be concise and relaxed like a strong squadmate speaking between fights, not military roleplay.")

    if brain == "DEMON":
        instructions.append("In DEMON mode, be more decisive and information-dense while keeping the same natural speaking voice; never shout, growl or perform a villain persona, and never artificially lower the pitch.")
    elif brain == "PRO":
        instructions.append("In PRO mode, be precise and confident without becoming formal or announcer-like.")

    if emotion in {"TILT", "ANGRY", "ANXIOUS"}:
        instructions.append("lower the energy slightly and make the key correction especially clear.")
    elif emotion in {"HYPE", "EXCITED"}:
        instructions.append("Allow a little more energy while keeping the delivery conversational.")

    content = _content_direction(text)
    if content:
        instructions.append(content)
    return " ".join(part for part in instructions if part)


def voice_speed(profile: Mapping[str, Any] | None) -> float:
    """Compatibility-only semantic timing hint for legacy callers/tests.

    Cloud synthesis intentionally does not send a `speed` parameter; the model
    stays at native timing for the most natural result.
    """
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="").upper()
    emotion = _profile_value(data, "emotion", "emotional_state", fallback="CALM").upper()
    speed = 1.0
    if persona == "COACH" and brain:
        speed = 0.975
    if bool(data.get("_bco_voice_reply")):
        speed += 0.005
    if emotion in {"TILT", "ANGRY", "ANXIOUS"}:
        speed -= 0.02
    elif emotion in {"HYPE", "EXCITED"}:
        speed += 0.005
    return max(0.94, min(speed, 1.025))


class OpenAITTSBackend:
    def __init__(self, *, api_key: str, model: str = DEFAULT_TTS_MODEL, default_voice: str = DEFAULT_TTS_VOICE, timeout_s: float = 45.0, max_bytes: int = 20 * 1024 * 1024, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = str(api_key or "").strip()
        self.model = str(model or DEFAULT_TTS_MODEL).strip()[:120]
        self.default_voice = normalize_tts_voice(default_voice)
        self.max_bytes = max(256 * 1024, min(int(max_bytes or 0), 64 * 1024 * 1024))
        timeout = max(5.0, min(float(timeout_s or 45.0), 120.0))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(connect=min(timeout, 20.0), read=timeout, write=timeout, pool=timeout))

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self.model)

    def voice_for(self, profile: Mapping[str, Any] | None) -> str:
        data = dict(profile or {})
        explicit = str(data.get("tts_voice") or "").strip()
        if explicit:
            return normalize_tts_voice(explicit, self.default_voice)
        identity = normalize_voice_identity(data.get("voice_identity"))
        if identity:
            return IDENTITY_DEFAULT_VOICES[identity]
        return self.default_voice

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
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav, application/octet-stream",
            "User-Agent": "BLACK-CROWN-OPS/voice-natural-v40.4",
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
