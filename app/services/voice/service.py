# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from app.services.voice.audio import clean_tts_text, wav_to_ogg_opus
from app.services.voice.openai_backend import OpenAITTSBackend, normalize_tts_voice
from app.services.voice.piper_backend import PiperBackend, PiperModelManager

log = logging.getLogger("bco.voice.service")


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


def _bool_setting(settings: Any, name: str, default: bool) -> bool:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() not in {"0", "false", "off", "no", ""}


@dataclass
class VoiceArtifact:
    path: Path
    spoken_text: str
    temp_dir: Path
    provider: str = "unknown"
    voice_name: str = ""

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)


@dataclass
class VoiceService:
    settings: Any
    backend: Any = None
    cloud_backend: Any = None

    def __post_init__(self) -> None:
        self._provider_setting = str(getattr(self.settings, "voice_provider", "auto") or "auto").strip().casefold()
        self._high_fidelity_enabled = _bool_setting(self.settings, "voice_high_fidelity_enabled", True)
        self._local_fallback_enabled = _bool_setting(self.settings, "voice_local_fallback_enabled", True)
        self._opus_bitrate_kbps = max(
            32,
            min(int(getattr(self.settings, "voice_opus_bitrate_kbps", 48) or 48), 96),
        )

        if self.backend is None:
            manager = PiperModelManager(
                model_dir=getattr(self.settings, "voice_model_dir", ".bco_voice"),
                model_name=getattr(self.settings, "voice_model_name", "ru_RU-denis-medium"),
                timeout_s=getattr(self.settings, "voice_model_timeout_s", 120.0),
            )
            self.backend = PiperBackend(manager)

        self._owns_cloud_backend = False
        if self.cloud_backend is None and self._should_configure_cloud():
            self.cloud_backend = OpenAITTSBackend(
                api_key=str(getattr(self.settings, "openai_api_key", "") or ""),
                model=str(getattr(self.settings, "voice_openai_model", "gpt-4o-mini-tts") or "gpt-4o-mini-tts"),
                default_voice=str(getattr(self.settings, "voice_openai_voice", "cedar") or "cedar"),
                timeout_s=float(getattr(self.settings, "voice_openai_timeout_s", 45.0) or 45.0),
                max_bytes=int(
                    getattr(self.settings, "voice_openai_max_bytes", 20 * 1024 * 1024)
                    or 20 * 1024 * 1024
                ),
            )
            self._owns_cloud_backend = True

        self._lock = asyncio.Lock()

    def _should_configure_cloud(self) -> bool:
        if not self._high_fidelity_enabled:
            return False
        if self._provider_setting in {"local", "offline", "piper_only", "piper-only", "local_only"}:
            return False
        api_key = str(getattr(self.settings, "openai_api_key", "") or "").strip()
        return bool(api_key)

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.settings, "voice_enabled", True))

    @property
    def high_fidelity_active(self) -> bool:
        return bool(self.cloud_backend is not None and getattr(self.cloud_backend, "configured", True))

    def mode_for(self, profile: Mapping[str, Any] | None) -> TTSMode:
        return normalize_tts_mode((profile or {}).get("tts_mode"))

    def should_auto(self, profile: Mapping[str, Any] | None) -> bool:
        return self.enabled and self.mode_for(profile) == TTSMode.AUTO

    def voice_name_for(self, profile: Mapping[str, Any] | None = None) -> str:
        if self.high_fidelity_active and callable(getattr(self.cloud_backend, "voice_for", None)):
            try:
                return str(self.cloud_backend.voice_for(profile or {}))
            except Exception:
                pass
        requested = (profile or {}).get("tts_voice")
        if requested:
            return normalize_tts_voice(requested)
        local_name = getattr(self.backend, "model_name", None)
        if local_name:
            return str(local_name)
        manager = getattr(self.backend, "manager", None)
        return str(getattr(manager, "model_name", "local"))

    def describe(self, profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if self.high_fidelity_active:
            provider = "OPENAI HIGH-FIDELITY"
            fallback = bool(self._local_fallback_enabled and self.backend is not None)
        else:
            provider = "PIPER LOCAL"
            fallback = False
        return {
            "provider": provider,
            "voice": self.voice_name_for(profile).upper(),
            "local_fallback": fallback,
        }

    async def close(self) -> None:
        if self.cloud_backend is None:
            return
        close = getattr(self.cloud_backend, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result

    async def _cloud_wav(
        self,
        text: str,
        wav_path: Path,
        profile: Mapping[str, Any],
    ) -> bool:
        if not self.high_fidelity_active:
            return False
        synthesize = getattr(self.cloud_backend, "synthesize_wav", None)
        if not callable(synthesize):
            return False
        try:
            result = synthesize(text, wav_path, profile)
            if asyncio.iscoroutine(result):
                await result
            return wav_path.exists() and wav_path.stat().st_size > 44
        except Exception as exc:
            log.warning("high-fidelity voice failed; using local fallback error=%s", type(exc).__name__)
            return False

    async def _local_wav(
        self,
        text: str,
        wav_path: Path,
        profile: Mapping[str, Any],
    ) -> None:
        if self.backend is None or not self._local_fallback_enabled:
            raise RuntimeError("Local voice fallback is unavailable")
        await asyncio.to_thread(self.backend.synthesize_wav, text, wav_path, dict(profile))

    async def synthesize(self, text: str, profile: Mapping[str, Any] | None = None) -> VoiceArtifact:
        if not self.enabled:
            raise RuntimeError("Voice/TTS is disabled")
        spoken = clean_tts_text(text, int(getattr(self.settings, "voice_max_chars", 1800) or 1800))
        if not spoken:
            raise ValueError("Nothing useful to synthesize")

        data = dict(profile or {})
        temp_dir = Path(tempfile.mkdtemp(prefix="bco-voice-"))
        wav_path = temp_dir / "reply.wav"
        ogg_path = temp_dir / "reply.ogg"
        provider = "piper"
        voice_name = self.voice_name_for(data)
        try:
            async with self._lock:
                cloud_ok = await self._cloud_wav(spoken, wav_path, data)
                if cloud_ok:
                    provider = "openai"
                    voice_name = self.voice_name_for(data)
                else:
                    await self._local_wav(spoken, wav_path, data)
                    provider = "piper"
                    local_name = getattr(self.backend, "model_name", None)
                    if local_name:
                        voice_name = str(local_name)
                await asyncio.to_thread(
                    wav_to_ogg_opus,
                    wav_path,
                    ogg_path,
                    data,
                    self._opus_bitrate_kbps,
                )
            return VoiceArtifact(
                path=ogg_path,
                spoken_text=spoken,
                temp_dir=temp_dir,
                provider=provider,
                voice_name=voice_name,
            )
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
