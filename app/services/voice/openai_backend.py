# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Mapping

import httpx

log = logging.getLogger("bco.voice.openai")

OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "cedar"
ALLOWED_TTS_VOICES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
        "marin",
        "cedar",
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


def voice_instructions(profile: Mapping[str, Any] | None) -> str:
    """Build a safe, non-impersonating performance direction for the TTS model."""
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="NORMAL").upper()

    instructions = [
        "Speak in fluent, natural Russian with a neutral native Russian accent.",
        "Use calm confidence, clean diction, natural breathing and human conversational prosody.",
        "Pronounce English gaming terms clearly inside Russian speech.",
        "Never sound robotic, theatrical, like an advertisement, or like a real named person.",
        "Use short purposeful pauses between tactical points and do not read decorative symbols aloud.",
    ]

    if persona == "COACH":
        instructions.extend(
            [
                "Sound like an experienced analytical esports coach.",
                "Use a measured pace, warm authority and slightly stronger emphasis on causes and next actions.",
            ]
        )
    else:
        instructions.extend(
            [
                "Sound like a trusted squad teammate speaking over clear voice chat.",
                "Keep the pace slightly brisk, direct and concise without shouting or fake radio distortion.",
            ]
        )

    if brain == "DEMON":
        instructions.append(
            "Add restrained intensity and decisiveness, while staying controlled and easy to understand."
        )
    elif brain == "PRO":
        instructions.append("Use precise emphasis and a focused professional tone.")

    return " ".join(instructions)


def voice_speed(profile: Mapping[str, Any] | None) -> float:
    data = dict(profile or {})
    persona = _profile_value(data, "voice", "voice_mode", fallback="TEAMMATE").upper()
    brain = _profile_value(data, "difficulty", "brain_mode", fallback="NORMAL").upper()
    speed = 0.98 if persona == "COACH" else 1.04
    if brain == "DEMON":
        speed += 0.01
    return max(0.85, min(speed, 1.15))


class OpenAITTSBackend:
    """Steerable high-fidelity speech backend using OpenAI's Audio API.

    The backend requests WAV so the same mastering/Opus pipeline is applied to
    cloud and local voices before Telegram delivery.
    """

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
        return normalize_tts_voice((profile or {}).get("tts_voice"), self.default_voice)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _download_once(
        self,
        *,
        text: str,
        output: Path,
        profile: Mapping[str, Any],
    ) -> Path:
        if not self.configured:
            raise RuntimeError("OpenAI TTS is not configured")

        payload = {
            "model": self.model,
            "voice": self.voice_for(profile),
            "input": str(text or "")[:4096],
            "instructions": voice_instructions(profile)[:4096],
            "response_format": "wav",
            "speed": voice_speed(profile),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav, application/octet-stream",
            "User-Agent": "BLACK-CROWN-OPS/voice-v17",
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        part = output.with_suffix(output.suffix + ".part")
        part.unlink(missing_ok=True)
        total = 0
        try:
            async with self._client.stream(
                "POST",
                OPENAI_SPEECH_URL,
                headers=headers,
                json=payload,
            ) as response:
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

    async def synthesize_wav(
        self,
        text: str,
        output_path: str | Path,
        profile: Mapping[str, Any] | None = None,
    ) -> Path:
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
