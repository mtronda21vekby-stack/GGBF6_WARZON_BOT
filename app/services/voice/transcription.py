# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("bco.voice.transcription")

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"

_GAME_PROMPT = (
    "Это голосовое сообщение игрока BLACK CROWN OPS. Ожидай русский язык, английский FPS-сленг "
    "и названия игр/терминов: Warzone, Black Ops 7, BO7, Battlefield 6, BF6, Zombies, Ashes of the Damned, "
    "Astra Malorum, ranked, resurgence, loadout, meta, aim assist, ADS, TTK, FOV, FPS, K/D, KD, VOD, KBM, "
    "controller, rotation, rotate, push, flank, entry, IGL, support, flex, slide cancel, recoil, sensitivity. "
    "Сохраняй смысл, числа, названия оружия и игровой сленг. Не добавляй слова, которых нет в аудио."
)


class TranscriptionError(RuntimeError):
    pass


class OpenAITranscriptionBackend:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_TRANSCRIPTION_MODEL,
        timeout_s: float = 45.0,
        max_bytes: int = 12 * 1024 * 1024,
        prompt: str = _GAME_PROMPT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self.model = str(model or DEFAULT_TRANSCRIPTION_MODEL).strip()[:120]
        self.max_bytes = max(256 * 1024, min(int(max_bytes or 0), 25 * 1024 * 1024))
        self.prompt = str(prompt or _GAME_PROMPT).strip()[:4096]
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

    async def _transcribe_once(self, path: Path) -> str:
        if not self.configured:
            raise TranscriptionError("Speech transcription is not configured")
        if not path.exists() or path.stat().st_size <= 0:
            raise TranscriptionError("Voice file is empty")
        if path.stat().st_size > self.max_bytes:
            raise TranscriptionError("Voice file exceeds transcription size limit")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": "BLACK-CROWN-OPS/voice-intelligence-v19",
        }
        data = {
            "model": self.model,
            "response_format": "json",
            "prompt": self.prompt,
        }
        with path.open("rb") as handle:
            files = {"file": (path.name, handle, "audio/ogg")}
            response = await self._client.post(
                OPENAI_TRANSCRIPTION_URL,
                headers=headers,
                data=data,
                files=files,
            )
        response.raise_for_status()
        payload: Any = response.json()
        text = str((payload or {}).get("text") or "").strip() if isinstance(payload, dict) else ""
        if not text:
            raise TranscriptionError("Speech transcription returned empty text")
        return text

    async def transcribe(self, path: str | Path) -> str:
        source = Path(path)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                return await self._transcribe_once(source)
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
        raise TranscriptionError("Speech transcription failed") from last_error
