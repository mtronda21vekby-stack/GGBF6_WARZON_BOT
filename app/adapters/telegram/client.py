from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from app.ui.presentation import polish_telegram_text


class TelegramClient:
    def __init__(self, bot_token: str):
        self._token = bot_token
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._file_base = f"https://api.telegram.org/file/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=60)

    async def close(self) -> None:
        await self._client.aclose()

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        payload: dict = {
            "chat_id": chat_id,
            "text": polish_telegram_text(text),
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        response = await self._client.post(f"{self._base}/sendMessage", json=payload)
        response.raise_for_status()

    async def send_voice_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Voice file not found: {file_path}")
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        with open(file_path, "rb") as file_handle:
            files = {"voice": (os.path.basename(file_path), file_handle, "audio/ogg")}
            response = await self._client.post(f"{self._base}/sendVoice", data=data, files=files)
            response.raise_for_status()

    async def get_file(self, file_id: str) -> dict:
        normalized_file_id = str(file_id or "").strip()
        if not normalized_file_id:
            raise ValueError("empty Telegram file_id")
        response = await self._client.post(
            f"{self._base}/getFile",
            json={"file_id": normalized_file_id},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("ok"):
            description = str((payload or {}).get("description") or "Telegram getFile failed")
            raise RuntimeError(description)
        result = payload.get("result") or {}
        if not isinstance(result, dict) or not result.get("file_path"):
            raise RuntimeError("Telegram getFile returned no file_path")
        return result

    async def download_file(
        self,
        file_id: str,
        destination: str,
        *,
        max_bytes: int = 20 * 1024 * 1024,
        timeout_s: float = 60.0,
    ) -> dict:
        info = await self.get_file(file_id)
        declared_size = int(info.get("file_size") or 0)
        limit = max(1, int(max_bytes or 1))
        if declared_size and declared_size > limit:
            raise ValueError(f"Telegram file is too large: {declared_size} bytes > {limit}")
        file_path = str(info.get("file_path") or "").lstrip("/")
        if not file_path:
            raise RuntimeError("Telegram file_path is empty")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        timeout = httpx.Timeout(
            connect=min(max(float(timeout_s), 5.0), 30.0),
            read=max(float(timeout_s), 10.0),
            write=max(float(timeout_s), 10.0),
            pool=max(float(timeout_s), 10.0),
        )
        try:
            async with self._client.stream(
                "GET",
                f"{self._file_base}/{file_path}",
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                header_size = int(response.headers.get("content-length") or 0)
                if header_size and header_size > limit:
                    raise ValueError(f"Telegram file is too large: {header_size} bytes > {limit}")
                with target.open("wb") as file_handle:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > limit:
                            raise ValueError(f"Telegram file exceeded {limit} bytes while downloading")
                        file_handle.write(chunk)
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        if total <= 0:
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            raise RuntimeError("Telegram downloaded an empty file")
        return {**info, "downloaded_bytes": total, "destination": str(target)}

    async def send_animation_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Animation file not found: {file_path}")
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        with open(file_path, "rb") as file_handle:
            files = {"animation": (os.path.basename(file_path), file_handle, "video/mp4")}
            response = await self._client.post(f"{self._base}/sendAnimation", data=data, files=files)
            response.raise_for_status()

    async def send_video_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        with open(file_path, "rb") as file_handle:
            files = {"video": (os.path.basename(file_path), file_handle, "video/mp4")}
            response = await self._client.post(f"{self._base}/sendVideo", data=data, files=files)
            response.raise_for_status()
