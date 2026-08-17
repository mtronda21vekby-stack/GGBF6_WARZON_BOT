# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import math
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("bco.voice.transcription")

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
DEFAULT_FALLBACK_MODEL = "gpt-4o-mini-transcribe"

_GAME_PROMPT = (
    "Это голосовое сообщение игрока BLACK CROWN OPS. Ожидай русский язык с естественным английским FPS-сленгом "
    "и названия игр/терминов: Warzone, Black Ops 7, BO7, Battlefield 6, BF6, Zombies, Ashes of the Damned, "
    "Astra Malorum, ranked, resurgence, loadout, meta, aim assist, ADS, TTK, FOV, FPS, K/D, KD, VOD, KBM, "
    "controller, rotation, rotate, push, flank, entry, IGL, support, flex, slide cancel, recoil, sensitivity, "
    "headglitch, chall, ego chall, centering, tracking, flick, deadzone, response curve. "
    "Сохраняй смысл, отрицания, числа, названия оружия, карт, режимов и игровой сленг. "
    "Не исправляй тактический смысл и не добавляй слов, которых нет в аудио."
)


class TranscriptionError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    confidence: float | None
    model: str
    language: str
    fallback_used: bool = False

    @property
    def confidence_percent(self) -> int | None:
        if self.confidence is None:
            return None
        return int(round(max(0.0, min(1.0, self.confidence)) * 100))


def _confidence_from_logprobs(payload: dict[str, Any]) -> float | None:
    raw = payload.get("logprobs")
    if not isinstance(raw, list):
        return None
    values: list[float] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            value = float(item.get("logprob"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(max(-20.0, min(0.0, value)))
    if not values:
        return None
    # Geometric mean of token probabilities is stable across transcript length.
    return max(0.0, min(1.0, math.exp(sum(values) / len(values))))


def _audio_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed.startswith("audio/"):
        return guessed
    suffix = path.suffix.casefold()
    return {
        ".ogg": "audio/ogg",
        ".oga": "audio/ogg",
        ".opus": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".flac": "audio/flac",
    }.get(suffix, "application/octet-stream")


class OpenAITranscriptionBackend:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_TRANSCRIPTION_MODEL,
        fallback_model: str = DEFAULT_FALLBACK_MODEL,
        timeout_s: float = 45.0,
        max_bytes: int = 12 * 1024 * 1024,
        prompt: str = _GAME_PROMPT,
        language: str = "ru",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self.model = str(model or DEFAULT_TRANSCRIPTION_MODEL).strip()[:120]
        self.fallback_model = str(fallback_model or DEFAULT_FALLBACK_MODEL).strip()[:120]
        self.max_bytes = max(256 * 1024, min(int(max_bytes or 0), 25 * 1024 * 1024))
        self.prompt = str(prompt or _GAME_PROMPT).strip()[:4096]
        self.language = str(language or "ru").strip().lower()[:8]
        timeout = max(5.0, min(float(timeout_s or 45.0), 120.0))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=min(timeout, 20.0), read=timeout, write=timeout, pool=timeout)
        )

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self.model)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, path: Path, *, model: str, include_logprobs: bool) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": "BLACK-CROWN-OPS/voice-studio-v21",
        }
        # httpx multipart encoding expects mapping-like form data when files are
        # present. A list of tuples can fail client-side before any HTTP request,
        # which used to surface to Telegram as a generic "voice unavailable".
        fields: dict[str, str] = {
            "model": model,
            "response_format": "json",
            "prompt": self.prompt,
        }
        if self.language:
            fields["language"] = self.language
        if include_logprobs:
            fields["include[]"] = "logprobs"

        with path.open("rb") as handle:
            files = {"file": (path.name, handle, _audio_mime(path))}
            response = await self._client.post(
                OPENAI_TRANSCRIPTION_URL,
                headers=headers,
                data=fields,
                files=files,
            )
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict):
            raise TranscriptionError("Speech transcription returned an invalid response")
        return payload

    async def _transcribe_model(self, path: Path, *, model: str, fallback_used: bool) -> TranscriptionResult:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                try:
                    payload = await self._request(path, model=model, include_logprobs=True)
                except httpx.HTTPStatusError as exc:
                    # Some compatible/self-hosted endpoints may not understand
                    # the logprobs include field. Keep transcription available.
                    if exc.response.status_code == 400:
                        payload = await self._request(path, model=model, include_logprobs=False)
                    else:
                        raise
                text = str(payload.get("text") or "").strip()
                if not text:
                    raise TranscriptionError("Speech transcription returned empty text")
                return TranscriptionResult(
                    text=text,
                    confidence=_confidence_from_logprobs(payload),
                    model=model,
                    language=self.language or "auto",
                    fallback_used=fallback_used,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = int(exc.response.status_code)
                if attempt == 0 and (status == 429 or status >= 500):
                    await asyncio.sleep(0.35)
                    continue
                raise TranscriptionError(f"Speech transcription HTTP {status}") from exc
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.35)
                    continue
                raise TranscriptionError("Speech transcription network failure") from exc
            except TranscriptionError:
                raise
            except Exception as exc:
                # Normalize transport/encoding errors into the STT boundary so
                # ingress can return an actionable retry instead of crashing the
                # entire voice pre-handler.
                raise TranscriptionError("Speech transcription transport failure") from exc
        raise TranscriptionError("Speech transcription failed") from last_error

    async def transcribe_result(self, path: str | Path) -> TranscriptionResult:
        if not self.configured:
            raise TranscriptionError("Speech transcription is not configured")
        source = Path(path)
        if not source.exists() or source.stat().st_size <= 0:
            raise TranscriptionError("Voice file is empty")
        if source.stat().st_size > self.max_bytes:
            raise TranscriptionError("Voice file exceeds transcription size limit")

        try:
            return await self._transcribe_model(source, model=self.model, fallback_used=False)
        except TranscriptionError as primary_error:
            fallback = self.fallback_model
            if not fallback or fallback == self.model:
                raise
            log.warning(
                "primary transcription failed; trying fallback primary=%s fallback=%s error=%s",
                self.model,
                fallback,
                type(primary_error).__name__,
            )
            return await self._transcribe_model(source, model=fallback, fallback_used=True)

    async def transcribe(self, path: str | Path) -> str:
        """Backward-compatible text-only facade."""
        return (await self.transcribe_result(path)).text
