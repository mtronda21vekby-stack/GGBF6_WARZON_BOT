from __future__ import annotations

import asyncio
import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.voice.service import TTSMode, VoiceService, normalize_tts_mode


def _write_wav(path: Path, frequency: float = 330.0) -> Path:
    rate = 22050
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * 0.12)):
            frames.extend(struct.pack("<h", int(5000 * math.sin(2 * math.pi * frequency * i / rate))))
        wav.writeframes(bytes(frames))
    return path


class FakeBackend:
    model_name = "ru_RU-test-medium"

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def synthesize_wav(self, text: str, output_path: str | Path, profile=None):
        self.calls.append((text, dict(profile or {})))
        return _write_wav(Path(output_path), 330.0)


class FakeCloud:
    configured = True

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[str, dict]] = []

    def voice_for(self, profile):
        return str((profile or {}).get("tts_voice") or "marin")

    async def synthesize_wav(self, text: str, output_path: str | Path, profile=None):
        self.calls.append((text, dict(profile or {})))
        if self.fail:
            raise RuntimeError("cloud unavailable")
        return _write_wav(Path(output_path), 440.0)

    async def close(self):
        return None


def _settings(**overrides):
    base = dict(
        voice_enabled=True,
        voice_follow_input_enabled=True,
        voice_provider="auto",
        voice_high_fidelity_enabled=True,
        voice_local_fallback_enabled=True,
        voice_max_chars=500,
        voice_duplex_max_chars=500,
        voice_opus_bitrate_kbps=48,
        voice_model_dir=".bco_voice",
        voice_model_name="ru_RU-denis-medium",
        voice_model_timeout_s=120.0,
        voice_openai_model="gpt-4o-mini-tts",
        voice_openai_voice="marin",
        voice_openai_timeout_s=45.0,
        voice_openai_max_bytes=20 * 1024 * 1024,
        openai_api_key="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_tts_mode_normalization():
    assert normalize_tts_mode("auto") == TTSMode.AUTO
    assert normalize_tts_mode("on-demand") == TTSMode.ON_DEMAND
    assert normalize_tts_mode(None) == TTSMode.OFF


def test_local_voice_uses_rescue_master_and_generates_ogg():
    local = FakeBackend()
    service = VoiceService(_settings(), backend=local)
    artifact = asyncio.run(service.synthesize("🎯 Проверка голосового ответа.", {"voice": "TEAMMATE"}))
    try:
        assert artifact.path.exists()
        assert artifact.path.read_bytes()[:4] == b"OggS"
        assert "Проверка" in artifact.spoken_text
        assert artifact.provider == "piper"
        assert artifact.voice_name == "ru_RU-test-medium"
        assert artifact.mastering == "piper-rescue-v2"
        assert artifact.opus_bitrate_kbps == 48
        assert len(local.calls) == 1
    finally:
        temp = artifact.temp_dir
        artifact.cleanup()
        assert not temp.exists()


def test_high_fidelity_cloud_voice_uses_transparent_natural_mastering():
    local = FakeBackend()
    cloud = FakeCloud()
    service = VoiceService(_settings(), backend=local, cloud_backend=cloud)

    artifact = asyncio.run(
        service.synthesize(
            "Держи высоту и ротируйся раньше.",
            {"voice": "COACH", "difficulty": "PRO", "tts_voice": "marin"},
        )
    )
    try:
        assert artifact.path.read_bytes()[:4] == b"OggS"
        assert artifact.provider == "openai"
        assert artifact.voice_name == "marin"
        assert artifact.mastering == "natural-v3"
        assert len(cloud.calls) == 1
        assert local.calls == []
        description = service.describe({"tts_voice": "marin"})
        assert description == {
            "provider": "OPENAI NATURAL VOICE",
            "voice": "MARIN",
            "local_fallback": True,
            "mastering": "NATURAL MASTER V3",
            "opus_bitrate_kbps": 48,
            "cloud_processing": "transparent",
        }
    finally:
        artifact.cleanup()


def test_cloud_failure_falls_back_to_local_voice_without_losing_reply():
    local = FakeBackend()
    cloud = FakeCloud(fail=True)
    service = VoiceService(_settings(), backend=local, cloud_backend=cloud)

    artifact = asyncio.run(
        service.synthesize(
            "Связь восстановлена.",
            {"voice": "TEAMMATE", "tts_voice": "cedar"},
        )
    )
    try:
        assert artifact.path.read_bytes()[:4] == b"OggS"
        assert artifact.provider == "piper"
        assert artifact.voice_name == "ru_RU-test-medium"
        assert artifact.mastering == "piper-rescue-v2"
        assert len(cloud.calls) == 1
        assert len(local.calls) == 1
    finally:
        artifact.cleanup()


def test_voice_service_respects_disabled_switch():
    service = VoiceService(_settings(voice_enabled=False), backend=FakeBackend())
    try:
        asyncio.run(service.synthesize("test", {}))
        raise AssertionError("expected disabled voice to fail")
    except RuntimeError as exc:
        assert "disabled" in str(exc).lower()


def test_surface_neutral_wave_reuses_cloud_and_russian_piper_fallback():
    cloud_service = VoiceService(_settings(), backend=FakeBackend(), cloud_backend=FakeCloud())
    cloud = asyncio.run(cloud_service.synthesize_wave("One. Two.", {"language": "en"}))
    try:
        assert cloud.path.read_bytes()[:4] == b"RIFF"
        assert cloud.quality == "canonical"
        assert cloud.provider == "openai"
    finally:
        cloud.cleanup()

    local_service = VoiceService(_settings(), backend=FakeBackend())
    local = asyncio.run(local_service.synthesize_wave("Первое. Второе.", {"language": "ru"}))
    try:
        assert local.path.read_bytes()[:4] == b"RIFF"
        assert local.quality == "fallback"
        assert local.provider == "piper"
    finally:
        local.cleanup()


def test_local_russian_voice_does_not_falsely_claim_english_support():
    service = VoiceService(_settings(), backend=FakeBackend())
    with pytest.raises(RuntimeError, match="English fallback"):
        asyncio.run(service.synthesize_wave("One. Two.", {"language": "en"}))
