from __future__ import annotations

import asyncio
import io
import json
import math
import struct
import wave
from pathlib import Path

import httpx

from app.services.voice.openai_backend import (
    OpenAITTSBackend,
    normalize_tts_voice,
    voice_instructions,
    voice_speed,
)


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    rate = 22050
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * 0.08)):
            frames.extend(struct.pack("<h", int(4000 * math.sin(2 * math.pi * 440 * i / rate))))
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


def test_voice_normalization_defaults_to_marin_and_profile_direction_is_bounded():
    assert normalize_tts_voice("MARIN") == "marin"
    assert normalize_tts_voice("CORAL") == "coral"
    assert normalize_tts_voice("SHIMMER") == "shimmer"
    assert normalize_tts_voice("not-a-real-voice") == "marin"

    coach = voice_instructions({"voice": "COACH", "difficulty": "PRO", "tts_voice": "marin"})
    teammate = voice_instructions({"voice": "TEAMMATE", "difficulty": "DEMON", "tts_voice": "cedar"})

    assert "natural Russian" in coach
    assert "one person" in coach
    assert "COACH" in coach
    assert "TEAMMATE" in teammate
    assert "spontaneous close conversation" in teammate
    assert voice_speed({"voice": "COACH"}) == 0.975
    assert voice_speed({"voice": "TEAMMATE"}) == 1.0


def test_user_selected_voice_is_authoritative_and_persona_does_not_swap_it():
    backend = OpenAITTSBackend(api_key="test", default_voice="marin")
    try:
        assert backend.voice_for({"voice": "COACH"}) == "marin"
        assert backend.voice_for({"voice": "TEAMMATE"}) == "marin"
        assert backend.voice_for({"voice": "COACH", "tts_voice": "shimmer"}) == "shimmer"
        assert backend.voice_for({"voice": "TEAMMATE", "tts_voice": "coral"}) == "coral"
        assert backend.voice_for({"tts_voice": "cedar"}) == "cedar"
    finally:
        asyncio.run(backend.close())


def test_openai_backend_requests_wav_with_selected_voice_and_natural_instructions(tmp_path: Path):
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "path": request.url.path,
                "authorization": request.headers.get("authorization"),
                "payload": json.loads(request.content.decode("utf-8")),
            }
        )
        return httpx.Response(
            200,
            headers={"content-type": "audio/wav"},
            content=_wav_bytes(),
        )

    async def scenario() -> Path:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        backend = OpenAITTSBackend(
            api_key="test-secret",
            model="gpt-4o-mini-tts",
            default_voice="marin",
            client=client,
        )
        output = tmp_path / "speech.wav"
        try:
            await backend.synthesize_wav(
                "Держи высоту и не отдавай центр.",
                output,
                {"voice": "COACH", "difficulty": "PRO", "tts_voice": "coral"},
            )
            return output
        finally:
            await client.aclose()

    output = asyncio.run(scenario())

    assert output.exists()
    assert output.read_bytes()[:4] == b"RIFF"
    assert output.read_bytes()[8:12] == b"WAVE"
    assert len(requests) == 1
    request = requests[0]
    assert request["path"] == "/v1/audio/speech"
    assert request["authorization"] == "Bearer test-secret"
    payload = request["payload"]
    assert payload["model"] == "gpt-4o-mini-tts"
    assert payload["voice"] == "coral"
    assert payload["response_format"] == "wav"
    assert payload["speed"] == 0.975
    assert "natural Russian" in payload["instructions"]
    assert "CORAL" in payload["instructions"]
    assert "spontaneous close conversation" in payload["instructions"]
    assert payload["input"] == "Держи высоту и не отдавай центр."


def test_openai_backend_rejects_non_wav_payload(tmp_path: Path):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not audio")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        backend = OpenAITTSBackend(api_key="test-secret", client=client)
        try:
            await backend.synthesize_wav("test", tmp_path / "bad.wav", {})
        finally:
            await client.aclose()

    try:
        asyncio.run(scenario())
        raise AssertionError("expected invalid audio to fail")
    except RuntimeError as exc:
        assert "empty audio" in str(exc).lower() or "invalid wav" in str(exc).lower()
    assert not (tmp_path / "bad.wav").exists()
