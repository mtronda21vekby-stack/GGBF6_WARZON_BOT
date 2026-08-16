from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from app.adapters.telegram.client import TelegramClient


def test_send_voice_file_uses_sendvoice(tmp_path):
    voice_path = tmp_path / "voice.ogg"
    voice_path.write_bytes(b"OggSfake")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = TelegramClient("TEST")
    old = client._client
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=10)
    asyncio.run(old.aclose())
    try:
        asyncio.run(client.send_voice_file(42, str(voice_path)))
    finally:
        asyncio.run(client.close())

    assert seen["url"].endswith("/botTEST/sendVoice")
    assert b"voice.ogg" in seen["body"]
