from __future__ import annotations

from app.services.voice.openai_backend import OpenAITTSBackend, voice_instructions, voice_speed


def test_default_timbre_is_stable_and_player_selection_is_authoritative():
    backend = OpenAITTSBackend(api_key="test-key", default_voice="marin")
    try:
        assert backend.voice_for({"voice": "TEAMMATE"}) == "marin"
        assert backend.voice_for({"voice": "COACH"}) == "marin"
        assert backend.voice_for({"voice": "COACH", "tts_voice": "shimmer"}) == "shimmer"
        assert backend.voice_for({"voice": "TEAMMATE", "tts_voice": "coral"}) == "coral"
        assert backend.voice_for({"voice": "COACH", "tts_voice": "cedar"}) == "cedar"
    finally:
        import asyncio
        asyncio.run(backend.close())


def test_coach_delivery_is_slightly_slower_without_redefining_the_voice():
    coach = {"voice": "COACH", "difficulty": "PRO", "tts_voice": "marin"}
    teammate = {"voice": "TEAMMATE", "difficulty": "PRO", "tts_voice": "marin"}

    assert voice_speed(coach) < voice_speed(teammate)
    assert "As COACH" in voice_instructions(coach)
    assert "root cause and next correction" in voice_instructions(coach)
    assert "As TEAMMATE" in voice_instructions(teammate)
    assert "strong squadmate" in voice_instructions(teammate)


def test_tilt_reduces_speed_and_demon_stays_controlled():
    calm = {"voice": "TEAMMATE", "difficulty": "DEMON", "emotion": "CALM", "tts_voice": "marin"}
    tilt = {"voice": "TEAMMATE", "difficulty": "DEMON", "emotion": "TILT", "tts_voice": "marin"}

    assert voice_speed(tilt) < voice_speed(calm)
    instructions = voice_instructions(tilt)
    assert "lower the energy slightly" in instructions.lower()
    assert "never shout" in instructions
    assert "artificially lower the pitch" in instructions
