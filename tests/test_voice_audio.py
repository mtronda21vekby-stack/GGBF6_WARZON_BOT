from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from app.services.voice.audio import clean_tts_text, wav_to_ogg_opus


def _make_wav(path: Path) -> None:
    rate = 22050
    samples = int(rate * 0.18)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for i in range(samples):
            sample = int(8000 * math.sin(2 * math.pi * 440 * i / rate))
            frames.extend(struct.pack("<h", sample))
        wav.writeframes(bytes(frames))


def test_clean_tts_text_removes_brand_chrome_and_urls():
    text = "👑 BLACK CROWN OPS\n━━━━━━━━\n🎯 Причина: поздняя ротация.\n• Сдвинься раньше.\nhttps://example.com"
    out = clean_tts_text(text)
    assert "BLACK CROWN" not in out
    assert "http" not in out
    assert "Причина" in out
    assert "Сдвинься раньше" in out


def test_clean_tts_text_normalizes_fps_terms_for_russian_speech():
    text = (
        "FPS падает. K/D — 1.4. ADS слишком медленный: 180 ms. "
        "TTK вырос на 15%. Посмотри VOD и сыграй 1v1."
    )
    out = clean_tts_text(text)

    assert "эф-пи-эс" in out
    assert "кей-ди" in out
    assert "эй-ди-эс" in out
    assert "миллисекунд" in out
    assert "процентов" in out
    assert "ти-ти-кей" in out
    assert "вод" in out
    assert "один на один" in out


def test_clean_tts_text_preserves_sentence_flow_instead_of_period_per_line():
    text = "Проблема:\n• Ты поздно занял высоту\n• Потом отдал центр\nРешение: ротируйся раньше!"
    out = clean_tts_text(text)

    assert "Проблема:" in out
    assert "Ты поздно занял высоту." in out
    assert "Потом отдал центр." in out
    assert "Решение: ротируйся раньше!" in out
    assert ".." not in out


def test_wav_to_telegram_ogg_opus(tmp_path):
    wav_path = tmp_path / "input.wav"
    ogg_path = tmp_path / "voice.ogg"
    _make_wav(wav_path)
    out = wav_to_ogg_opus(
        wav_path,
        ogg_path,
        {"voice": "COACH", "difficulty": "PRO"},
        bitrate_kbps=48,
    )
    assert out.exists()
    assert out.stat().st_size > 100
    assert out.read_bytes()[:4] == b"OggS"
