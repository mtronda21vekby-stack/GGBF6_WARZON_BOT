from __future__ import annotations

from app.services.voice.openai_backend import OpenAITTSBackend, voice_instructions, voice_speed


def test_teammate_and_coach_receive_distinct_automatic_timbres():
    backend = OpenAITTSBackend(api_key="test-key", default_voice="cedar")
    try:
        assert backend.voice_for({"voice": "TEAMMATE"}) == "cedar"
        assert backend.voice_for({"voice": "COACH"}) == "marin"
        assert backend.voice_for({"voice": "COACH", "tts_voice": "onyx"}) == "onyx"
    finally:
        import asyncio
        asyncio.run(backend.close())


def test_coach_delivery_is_slower_and_more_analytical_than_teammate():
    coach = {"voice": "COACH", "difficulty": "PRO"}
    teammate = {"voice": "TEAMMATE", "difficulty": "PRO"}

    assert voice_speed(coach) < voice_speed(teammate)
    assert "elite esports coach" in voice_instructions(coach)
    assert "trusted high-level squad teammate" in voice_instructions(teammate)


def test_tilt_reduces_speed_and_demon_stays_controlled():
    calm = {"voice": "TEAMMATE", "difficulty": "DEMON", "emotion": "CALM"}
    tilt = {"voice": "TEAMMATE", "difficulty": "DEMON", "emotion": "TILT"}

    assert voice_speed(tilt) < voice_speed(calm)
    instructions = voice_instructions(tilt)
    assert "Lower emotional intensity" in instructions
    assert "restrained intensity" in instructions
