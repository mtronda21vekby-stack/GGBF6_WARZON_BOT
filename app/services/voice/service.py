# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from app.services.voice.audio import clean_tts_text, wav_to_ogg_opus
from app.services.voice.piper_backend import PiperBackend, PiperModelManager


class TTSMode(str, Enum):
    OFF = "OFF"
    AUTO = "AUTO"
    ON_DEMAND = "ON_DEMAND"


def normalize_tts_mode(value: Any) -> TTSMode:
    raw = str(value or "OFF").strip().upper().replace("-", "_").replace(" ", "_")
    if raw in {"AUTO", "AUTOMATIC"}:
        return TTSMode.AUTO
    if raw in {"ON_DEMAND", "ONDEMAND", "DEMAND", "MANUAL"}:
        return TTSMode.ON_DEMAND
    return TTSMode.OFF


@dataclass
class VoiceArtifact:
    path: Path
    spoken_text: str
    temp_dir: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)


@dataclass
class VoiceService:
    settings: Any
    backend: Any = None

    def __post_init__(self) -> None:
        if self.backend is None:
            manager = PiperModelManager(
                model_dir=getattr(self.settings, "voice_model_dir", ".bco_voice"),
                model_name=getattr(self.settings, "voice_model_name", "ru_RU-denis-medium"),
                timeout_s=getattr(self.settings, "voice_model_timeout_s", 120.0),
            )
            self.backend = PiperBackend(manager)
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.settings, "voice_enabled", True))

    def mode_for(self, profile: Mapping[str, Any] | None) -> TTSMode:
        return normalize_tts_mode((profile or {}).get("tts_mode"))

    def should_auto(self, profile: Mapping[str, Any] | None) -> bool:
        return self.enabled and self.mode_for(profile) == TTSMode.AUTO

    async def synthesize(self, text: str, profile: Mapping[str, Any] | None = None) -> VoiceArtifact:
        if not self.enabled:
            raise RuntimeError("Voice/TTS is disabled")
        spoken = clean_tts_text(text, int(getattr(self.settings, "voice_max_chars", 1600) or 1600))
        if not spoken:
            raise ValueError("Nothing useful to synthesize")

        temp_dir = Path(tempfile.mkdtemp(prefix="bco-voice-"))
        wav_path = temp_dir / "reply.wav"
        ogg_path = temp_dir / "reply.ogg"
        try:
            async with self._lock:
                await asyncio.to_thread(self.backend.synthesize_wav, spoken, wav_path, dict(profile or {}))
                await asyncio.to_thread(wav_to_ogg_opus, wav_path, ogg_path)
            return VoiceArtifact(path=ogg_path, spoken_text=spoken, temp_dir=temp_dir)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
