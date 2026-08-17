from __future__ import annotations

import math
from types import SimpleNamespace

from app.services.voice.openai_backend import voice_instructions
from app.services.voice.service import VoiceService
from app.services.voice.transcription import _confidence_from_logprobs


class DummyLocalBackend:
    model_name = "dummy-local"


def _settings(**overrides):
    values = {
        "voice_provider": "local",
        "voice_high_fidelity_enabled": False,
        "voice_local_fallback_enabled": True,
        "voice_follow_input_enabled": True,
        "voice_enabled": True,
        "voice_opus_bitrate_kbps": 64,
        "openai_api_key": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_transcription_confidence_uses_geometric_mean_token_probability():
    payload = {
        "logprobs": [
            {"token": "пуш", "logprob": math.log(0.9)},
            {"token": "ить", "logprob": math.log(0.8)},
        ]
    }
    confidence = _confidence_from_logprobs(payload)
    assert confidence is not None
    assert round(confidence, 3) == round(math.sqrt(0.9 * 0.8), 3)


def test_transcription_confidence_is_optional_when_provider_does_not_return_logprobs():
    assert _confidence_from_logprobs({"text": "hello"}) is None
    assert _confidence_from_logprobs({"logprobs": []}) is None


def test_smart_duplex_follows_voice_only_until_user_explicitly_sets_mode():
    service = VoiceService(settings=_settings(), backend=DummyLocalBackend())

    assert service.should_auto({}, input_mode="voice") is True
    assert service.should_auto({}, input_mode="voice_confirmed") is True
    assert service.should_auto({}, input_mode="text") is False
    assert service.should_auto({"tts_mode": "OFF"}, input_mode="voice") is False
    assert service.should_auto({"tts_mode": "ON_DEMAND"}, input_mode="voice") is False
    assert service.should_auto({"tts_mode": "AUTO"}, input_mode="text") is True


def test_duplex_follow_input_has_runtime_kill_switch():
    service = VoiceService(
        settings=_settings(voice_follow_input_enabled=False),
        backend=DummyLocalBackend(),
    )
    assert service.should_auto({}, input_mode="voice") is False


def test_short_reply_and_long_debrief_receive_distinct_natural_direction():
    profile = {"voice": "TEAMMATE", "difficulty": "PRO", "tts_voice": "marin"}
    short = voice_instructions(profile, "Два слева. Не пикай. Держи высоту.")
    long = voice_instructions(profile, "Причина ошибки. " * 90)

    assert "one natural short spoken reply" in short
    assert "longer answer" in long
    assert "natural conversational paragraph breaks" in long
    assert "read-out script" in short


def test_demon_adds_decisiveness_without_theatrical_delivery():
    instructions = voice_instructions(
        {"voice": "TEAMMATE", "difficulty": "DEMON", "tts_voice": "marin"},
        "Не выходи из сильной позиции ради одного килла.",
    )
    assert "more decisive" in instructions
    assert "never shout" in instructions
    assert "movie trailer" in instructions
    assert "artificially lower the pitch" in instructions
