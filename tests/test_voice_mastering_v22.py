from __future__ import annotations

from pathlib import Path

from app.services.voice.audio import (
    _master_profile,
    _one_pass_master_filter,
    clean_tts_text,
)
from app.services.voice.natural_audio import wav_to_natural_ogg_opus
from app.services.voice.openai_backend import voice_instructions, voice_speed


def test_legacy_studio_master_remains_available_only_for_local_piper_rescue():
    cfg = _master_profile({"voice": "TEAMMATE"})
    assert cfg["target_i"] == -16.0
    assert cfg["target_tp"] == -1.0
    assert cfg["target_lra"] == 5.5

    audio_filter = _one_pass_master_filter({"voice": "TEAMMATE"})
    assert "loudnorm=I=-16.0" in audio_filter
    assert "alimiter=" in audio_filter
    assert "highpass=f=58" in audio_filter
    assert "lowpass=f=14500" in audio_filter


def test_natural_cloud_encoder_is_separate_from_aggressive_piper_chain():
    source = Path(__file__).parents[1] / "app" / "services" / "voice" / "natural_audio.py"
    text = source.read_text(encoding="utf-8")
    assert "highpass=f=42" in text
    assert "alimiter=" in text
    assert "acompressor" not in text
    assert "equalizer=" not in text
    assert "loudnorm" not in text
    assert "libopus" in text
    assert '"-application",\n        "audio"' in text
    assert '"-application",\n        "voip"' not in text


def test_speech_cleaner_retains_paragraph_boundaries_for_prosody():
    source = (
        "◼ BLACK CROWN OPS // TEAMMATE\n"
        "Первый контакт: не отдавай высоту.\n\n"
        "После UAV ротируйся раньше. SMG держи для ближней дистанции."
    )
    result = clean_tts_text(source)

    assert "BLACK CROWN" not in result
    assert "\n\n" in result
    assert "ю-эй-ви" in result
    assert "эс-эм-джи" in result


def test_natural_voice_stays_near_native_model_timing():
    teammate = {"voice": "TEAMMATE", "difficulty": "PRO"}
    duplex = {**teammate, "_bco_voice_reply": True}
    tilted = {**duplex, "emotion": "TILT"}

    assert voice_speed(teammate) == 1.0
    assert voice_speed(duplex) == 1.005
    assert voice_speed(tilted) < voice_speed(duplex)
    assert 0.94 <= voice_speed(tilted) <= 1.025


def test_voice_direction_rejects_announcer_and_over_enunciation():
    instructions = voice_instructions(
        {"voice": "COACH", "difficulty": "DEMON", "tts_voice": "marin"},
        "Разбери ошибку при ротации и дай следующее действие.",
    )
    assert "natural Russian" in instructions
    assert "narrator" in instructions
    assert "movie trailer" in instructions
    assert "over-enunciate" in instructions
    assert "never shout" in instructions
    assert "real person" in instructions
    assert "repetitive falling cadence" in instructions
