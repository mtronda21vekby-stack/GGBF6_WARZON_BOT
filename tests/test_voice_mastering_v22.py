from __future__ import annotations

from app.services.voice.audio import (
    _master_profile,
    _one_pass_master_filter,
    clean_tts_text,
)
from app.services.voice.openai_backend import voice_instructions, voice_speed


def test_studio_master_targets_phone_and_headphone_voice_loudness():
    cfg = _master_profile({"voice": "TEAMMATE"})
    assert cfg["target_i"] == -16.0
    assert cfg["target_tp"] == -1.0
    assert cfg["target_lra"] == 5.5

    audio_filter = _one_pass_master_filter({"voice": "TEAMMATE"})
    assert "loudnorm=I=-16.0" in audio_filter
    assert "TP=-1.0" in audio_filter
    assert "alimiter=" in audio_filter
    assert "highpass=f=58" in audio_filter
    assert "lowpass=f=14500" in audio_filter


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


def test_duplex_voice_is_faster_but_bounded_and_tilt_slows_it_down():
    teammate = {"voice": "TEAMMATE", "difficulty": "PRO"}
    duplex = {**teammate, "_bco_voice_reply": True}
    tilted = {**duplex, "emotion": "TILT"}

    assert voice_speed(teammate) == 1.04
    assert voice_speed(duplex) > voice_speed(teammate)
    assert voice_speed(tilted) < voice_speed(duplex)
    assert 0.90 <= voice_speed(tilted) <= 1.08


def test_voice_direction_explicitly_rejects_trailer_and_radio_effects():
    instructions = voice_instructions(
        {"voice": "COACH", "difficulty": "DEMON"},
        "Разбери ошибку при ротации и дай следующее действие.",
    )
    assert "close-mic premium studio" in instructions
    assert "movie trailer" in instructions
    assert "radio distortion" in instructions
    assert "restrained intensity" in instructions
    assert "without shouting" in instructions
    assert "real named person" in instructions
