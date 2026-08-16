from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from app.ui.native_buttons import (
    contains_advanced_button_fields,
    decorate_reply_markup,
    strip_advanced_button_fields,
    upgrade_reply_keyboard_to_inline,
)
from app.ui.presentation import polish_telegram_text
from app.ui.rich_messages import tactical_rich_message


class TelegramClient:
    def __init__(self, bot_token: str):
        self._token = bot_token
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._file_base = f"https://api.telegram.org/file/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=60)

    async def close(self) -> None:
        await self._client.aclose()

    async def _post_json(self, method: str, payload: dict) -> httpx.Response:
        return await self._client.post(f"{self._base}/{method}", json=payload)

    @staticmethod
    def _prepare_markup(reply_markup: dict | None) -> dict | None:
        inline = upgrade_reply_keyboard_to_inline(reply_markup)
        return decorate_reply_markup(inline)

    @staticmethod
    def _is_not_modified(response: httpx.Response) -> bool:
        if response.status_code != 400:
            return False
        try:
            payload = response.json()
        except Exception:
            return False
        return "message is not modified" in str((payload or {}).get("description") or "").casefold()

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        polished = polish_telegram_text(text)
        styled_markup = self._prepare_markup(reply_markup)

        # Bot API 10.1+ renders BLACK CROWN cards as native structured rich
        # messages. A 400/404 falls back to ordinary text for compatibility
        # with an outdated self-hosted Bot API server.
        rich_message = tactical_rich_message(polished)
        if rich_message is not None:
            rich_payload: dict = {
                "chat_id": chat_id,
                "rich_message": rich_message,
            }
            if styled_markup is not None:
                rich_payload["reply_markup"] = styled_markup
            rich_response = await self._post_json("sendRichMessage", rich_payload)
            if rich_response.is_success:
                return
            if rich_response.status_code not in (400, 404):
                rich_response.raise_for_status()

        payload: dict = {
            "chat_id": chat_id,
            "text": polished,
            "disable_web_page_preview": True,
        }
        if styled_markup is not None:
            payload["reply_markup"] = styled_markup

        response = await self._post_json("sendMessage", payload)
        if response.is_success:
            return

        # Public Telegram already supports these fields. This retry protects a
        # private/local Bot API deployment that has not yet reached Bot API 9.4.
        if response.status_code == 400 and contains_advanced_button_fields(styled_markup):
            fallback_payload = dict(payload)
            fallback_markup = strip_advanced_button_fields(styled_markup)
            if fallback_markup is not None:
                fallback_payload["reply_markup"] = fallback_markup
            fallback = await self._post_json("sendMessage", fallback_payload)
            fallback.raise_for_status()
            return

        response.raise_for_status()

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        """Edit one console message in place, preserving rich/native UI when supported."""
        polished = polish_telegram_text(text)
        styled_markup = self._prepare_markup(reply_markup)
        rich_message = tactical_rich_message(polished)

        if rich_message is not None:
            rich_payload: dict[str, Any] = {
                "chat_id": int(chat_id),
                "message_id": int(message_id),
                "rich_message": rich_message,
            }
            if styled_markup is not None:
                rich_payload["reply_markup"] = styled_markup
            rich_response = await self._post_json("editMessageText", rich_payload)
            if rich_response.is_success or self._is_not_modified(rich_response):
                return
            if rich_response.status_code not in (400, 404):
                rich_response.raise_for_status()

        payload: dict[str, Any] = {
            "chat_id": int(chat_id),
            "message_id": int(message_id),
            "text": polished,
            "disable_web_page_preview": True,
        }
        if styled_markup is not None:
            payload["reply_markup"] = styled_markup

        response = await self._post_json("editMessageText", payload)
        if response.is_success or self._is_not_modified(response):
            return

        if response.status_code == 400 and contains_advanced_button_fields(styled_markup):
            fallback_payload = dict(payload)
            fallback_markup = strip_advanced_button_fields(styled_markup)
            if fallback_markup is not None:
                fallback_payload["reply_markup"] = fallback_markup
            fallback = await self._post_json("editMessageText", fallback_payload)
            if fallback.is_success or self._is_not_modified(fallback):
                return
            fallback.raise_for_status()
            return

        response.raise_for_status()

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        *,
        show_alert: bool = False,
        cache_time: int = 0,
    ) -> None:
        payload: dict[str, Any] = {
            "callback_query_id": str(callback_query_id),
            "show_alert": bool(show_alert),
            "cache_time": max(0, int(cache_time)),
        }
        if text:
            payload["text"] = str(text)[:200]
        response = await self._post_json("answerCallbackQuery", payload)
        response.raise_for_status()

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        response = await self._post_json(
            "deleteMessage",
            {"chat_id": int(chat_id), "message_id": int(message_id)},
        )
        response.raise_for_status()

    async def remove_reply_keyboard(self, chat_id: int) -> None:
        """Remove the legacy bottom keyboard without leaving a visible utility message."""
        response = await self._post_json(
            "sendMessage",
            {
                "chat_id": int(chat_id),
                "text": "\u2063",
                "disable_notification": True,
                "reply_markup": {"remove_keyboard": True},
            },
        )
        response.raise_for_status()
        try:
            payload = response.json()
            message_id = int(((payload or {}).get("result") or {}).get("message_id"))
        except Exception:
            return
        try:
            await self.delete_message(chat_id, message_id)
        except Exception:
            # The invisible message is harmless if Telegram rejects deletion.
            pass

    async def set_default_menu_button(self, text: str, webapp_url: str) -> None:
        url = str(webapp_url or "").strip()
        if not url.startswith("https://"):
            raise ValueError("Telegram WebApp menu button requires HTTPS")
        response = await self._post_json(
            "setChatMenuButton",
            {
                "menu_button": {
                    "type": "web_app",
                    "text": str(text or "COMMAND CENTER")[:64],
                    "web_app": {"url": url},
                }
            },
        )
        response.raise_for_status()

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        normalized: list[dict[str, str]] = []
        for item in list(commands or [])[:100]:
            command = str(item.get("command") or "").strip().lstrip("/")[:32]
            description = str(item.get("description") or "").strip()[:256]
            if command and description:
                normalized.append({"command": command, "description": description})
        if not normalized:
            return
        response = await self._post_json("setMyCommands", {"commands": normalized})
        response.raise_for_status()

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        response = await self._post_json(
            "sendChatAction",
            {"chat_id": int(chat_id), "action": str(action or "typing")},
        )
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
        styled_markup = self._prepare_markup(reply_markup)
        if styled_markup is not None:
            data["reply_markup"] = json.dumps(styled_markup, ensure_ascii=False)
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
        styled_markup = self._prepare_markup(reply_markup)
        if styled_markup is not None:
            data["reply_markup"] = json.dumps(styled_markup, ensure_ascii=False)
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
        styled_markup = self._prepare_markup(reply_markup)
        if styled_markup is not None:
            data["reply_markup"] = json.dumps(styled_markup, ensure_ascii=False)
        with open(file_path, "rb") as file_handle:
            files = {"video": (os.path.basename(file_path), file_handle, "video/mp4")}
            response = await self._client.post(f"{self._base}/sendVideo", data=data, files=files)
            response.raise_for_status()
