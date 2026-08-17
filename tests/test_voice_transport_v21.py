from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.services.voice.openai_backend import voice_instructions, voice_speed
from app.services.voice.service import VoiceService
from app.services.voice.transcription import OpenAITranscriptionBackend


def run(coro):
    return asyncio.run(coro)


def test_real_httpx_multipart_transport_reaches_openai_boundary(tmp_path: Path):
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = await request.aread()
        content_type = request.headers.get("content-type", "")
        assert content_type.startswith("multipart/form-data; boundary=")
        assert b'gpt-4o-transcribe' in body
        assert b'name="language"' in body
        assert b'ru' in body
        assert b'name="include[]"' in body
        assert b'logprobs' in body
        assert b'filename="voice.ogg"' in body
        return httpx.Response(
            200,
            json={
                "text": "Почему я умираю на ротации?",
                "logprobs": [{"logprob": -0.05}, {"logprob": -0.08}],
            },
        )

    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"OggS" + b"voice-data" * 20)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAITranscriptionBackend(
        api_key="test-key",
        model="gpt-4o-transcribe",
        fallback_model="gpt-4o-mini-transcribe",
        language="ru",
        client=client,
    )
    try:
        result = run(backend.transcribe_result(audio))
    finally:
        run(client.aclose())

    assert seen
    assert result.text == "Почему я умираю на ротации?"
    assert result.model == "gpt-4o-transcribe"
    assert result.confidence is not None and result.confidence > 0.9
    assert result.fallback_used is False


def test_transcription_retries_without_logprobs_on_compatible_400(tmp_path: Path):
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = await request.aread()
        if b'name="include[]"' in body:
            return httpx.Response(400, json={"error": {"message": "unsupported include"}})
        return httpx.Response(200, json={"text": "держать высоту"})

    audio = tmp_path / "voice.m4a"
    audio.write_bytes(b"fake-m4a" * 32)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = OpenAITranscriptionBackend(api_key="test-key", client=client)
    try:
        result = run(backend.transcribe_result(audio))
    finally:
        run(client.aclose())

    assert calls == 2
    assert result.text == "держать высоту"
    assert result.confidence is None


def test_voice_to_voice_direction_is_conversational_not_read_aloud():
    base = {
        "voice": "TEAMMATE",
        "difficulty": "Demon",
        "tts_voice": "marin",
    }
    typed = voice_instructions(base, "Держи высоту и не отдавай позицию.")
    duplex = voice_instructions(
        {**base, "_bco_voice_reply": True},
        "Держи высоту и не отдавай позицию.",
    )

    assert "directly answers the player's voice message" not in typed
    assert "directly answers the player's voice message" in duplex
    assert "avoid an intro or recap" in duplex
    assert "read-out script" in duplex
    assert voice_speed({**base, "_bco_voice_reply": True}) > voice_speed(base)


def test_duplex_voice_uses_shorter_spoken_budget_while_text_can_stay_full():
    class NoopBackend:
        model_name = "noop"

    settings = SimpleNamespace(
        voice_enabled=True,
        voice_provider="local",
        voice_high_fidelity_enabled=False,
        voice_local_fallback_enabled=True,
        voice_follow_input_enabled=True,
        voice_opus_bitrate_kbps=64,
        voice_max_chars=2200,
        voice_duplex_max_chars=700,
        voice_model_dir=".unused",
        voice_model_name="unused",
        voice_model_timeout_s=1,
    )
    service = VoiceService(settings=settings, backend=NoopBackend(), cloud_backend=None)

    assert service._speech_limit({}) == 2200
    assert service._speech_limit({"_bco_voice_reply": True}) == 700
