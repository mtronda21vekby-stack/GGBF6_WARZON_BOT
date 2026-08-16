import asyncio

import httpx

from app.adapters.telegram.client import TelegramClient


def test_telegram_file_download_is_bounded(tmp_path):
    async def run():
        def handler(request: httpx.Request):
            if request.url.path.endswith("/getFile"):
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "result": {
                            "file_id": "abc",
                            "file_path": "videos/a.mp4",
                            "file_size": 4,
                        },
                    },
                )
            if request.url.path.endswith("/videos/a.mp4"):
                return httpx.Response(200, content=b"data")
            return httpx.Response(404)

        tg = TelegramClient("TEST")
        await tg._client.aclose()
        tg._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        target = tmp_path / "clip.mp4"
        info = await tg.download_file("abc", str(target), max_bytes=10)
        assert target.read_bytes() == b"data"
        assert info["downloaded_bytes"] == 4
        await tg.close()

    asyncio.run(run())


def test_telegram_declared_oversize_is_rejected(tmp_path):
    async def run():
        def handler(request: httpx.Request):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "file_id": "abc",
                        "file_path": "videos/a.mp4",
                        "file_size": 50,
                    },
                },
            )

        tg = TelegramClient("TEST")
        await tg._client.aclose()
        tg._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await tg.download_file("abc", str(tmp_path / "clip.mp4"), max_bytes=10)
        except ValueError:
            pass
        else:
            raise AssertionError("expected size rejection")
        await tg.close()

    asyncio.run(run())
