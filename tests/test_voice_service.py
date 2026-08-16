from __future__ import annotations

import asyncio
import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

from app.services.voice.service import TTSMode, VoiceService, normalize_tts_mode


class FakeBackend:
    def synthesize_wav(self, text: str, output_path: str | Path, profile=None):
        path = Path(output_path)
        rate = 22050
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            frames = bytearray()
            for i in range(int(rate * 0.12)):
                frames.extend(struct.pack("<h", int(5000 * math.sin(2 * math.pi * 330 * i / rate))))
            wav.writeframes(bytes(frames))
        return path


def _settings(**overrides):
    base = dict(
        voice_enabled=True,
        voice_max_chars=500,
        voice_model_dir=".bco_voice",
        voice_model_name="ru_RU-denis-medium",
        voice_model_timeout_s=120.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_tts_mode_normalization():
    assert normalize_tts_mode("auto") == TTSMode.AUTO
    assert normalize_tts_mode("on-demand") == TTSMode.ON_DEMAND
    assert normalize_tts_mode(None) == TTSMode.OFF


def test_voice_service_generates_ogg_and_cleans_up():
    service = VoiceService(_settings(), backend=FakeBackend())
    artifact = asyncio.run(service.synthesize("🎯 Проверка голосового ответа.", {"voice": "TEAMMATE"}))
    try:
        assert artifact.path.exists()
        assert artifact.path.read_bytes()[:4] == b"OggS"
        assert "Проверка" in artifact.spoken_text
    finally:
        temp = artifact.temp_dir
        artifact.cleanup()
        assert not temp.exists()


def test_voice_service_respects_disabled_switch():
    service = VoiceService(_settings(voice_enabled=False), backend=FakeBackend())
    try:
        asyncio.run(service.synthesize("test", {}))
        raise AssertionError("expected disabled voice to fail")
    except RuntimeError as exc:
        assert "disabled" in str(exc).lower()
