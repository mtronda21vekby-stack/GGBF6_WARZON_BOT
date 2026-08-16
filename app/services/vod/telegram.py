# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.vod.service import (
    VODAnalysisService,
    VODCapabilityError,
    VODError,
    VODMedia,
    telegram_media_from_message,
)


log = logging.getLogger("bco.vod")


def _safe_ext(media: VODMedia) -> str:
    name = str(media.file_name or "").lower()
    for ext in (".mp4", ".mov", ".m4v", ".webm", ".mkv"):
        if name.endswith(ext):
            return ext
    mime = str(media.mime_type or "").lower()
    if "webm" in mime:
        return ".webm"
    if "quicktime" in mime:
        return ".mov"
    return ".mp4"


@dataclass
class VODTelegramIngress:
    tg: Any
    vod: VODAnalysisService
    profiles: Any
    store: Any
    player_memory: Any = None
    usage_guard: Any = None
    enabled: bool = True
    max_bytes: int = 20 * 1024 * 1024
    download_timeout_s: float = 60.0

    async def maybe_handle(self, update: dict[str, Any]) -> bool:
        callback = (update or {}).get("callback_query") or {}
        if isinstance(callback, dict) and callback:
            message = callback.get("message") or {}
            text = str(callback.get("data") or "").strip()
        else:
            message = (update or {}).get("message") or (update or {}).get("edited_message")
            text = str(message.get("text") or "").strip() if isinstance(message, dict) else ""
        if not isinstance(message, dict):
            return False
        chat_id = ((message.get("chat") or {}).get("id"))
        if chat_id is None:
            return False
        try:
            chat_id = int(chat_id)
        except Exception:
            return False

        if text in {"🎬 VOD", "🎬 VOD: Разбор"}:
            await self.tg.send_message(chat_id, self.vod.intro_text(self.max_bytes))
            return True

        media = telegram_media_from_message(message)
        if media is None:
            return False

        if not self.enabled:
            await self.tg.send_message(
                chat_id,
                "🎬 VOD media сейчас выключен на сервере. Таймкоды текстом по-прежнему работают.",
            )
            return True

        if media.file_size and media.file_size > self.max_bytes:
            mb = self.max_bytes // (1024 * 1024)
            await self.tg.send_message(
                chat_id,
                (
                    f"🎬 Видео принято, но стандартный Telegram Bot API не даст скачать файл больше {mb} MB.\n"
                    "Обрежь нужный эпизод/сожми клип и пришли снова. Лучше 20–90 секунд вокруг спорного момента."
                ),
            )
            return True

        # Charge only actual media analysis, not opening the VOD panel or
        # rejecting an oversized attachment.
        if self.usage_guard is not None:
            try:
                decision = self.usage_guard.check(chat_id, "vod")
                if not bool(getattr(decision, "allowed", True)):
                    wait = max(1, int(getattr(decision, "retry_after_s", 1) or 1))
                    await self.tg.send_message(
                        chat_id,
                        f"⏳ VOD-анализ сейчас на cooldown. Повтори примерно через {wait} сек.",
                    )
                    return True
            except Exception:
                pass

        note = str(message.get("caption") or "").strip()[:1200]
        await self.tg.send_message(
            chat_id,
            "🎬 VOD принят. Извлекаю контрольные кадры и запускаю тактический анализ…",
        )

        try:
            profile = self.profiles.get(chat_id) if self.profiles is not None else {}
        except Exception:
            profile = {}

        ext = _safe_ext(media)
        try:
            with tempfile.TemporaryDirectory(prefix="bco_vod_") as td:
                destination = str(Path(td) / f"input{ext}")
                await self.tg.download_file(
                    media.file_id,
                    destination,
                    max_bytes=self.max_bytes,
                    timeout_s=self.download_timeout_s,
                )
                result = await asyncio.to_thread(
                    self.vod.analyze_media,
                    destination,
                    media=media,
                    profile=dict(profile or {}),
                    note=note,
                )
        except ValueError as exc:
            await self.tg.send_message(chat_id, f"🎬 VOD не принят: {str(exc)[:300]}")
            return True
        except VODCapabilityError as exc:
            log.warning("vod capability unavailable chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                (
                    "🎬 Видео скачалось, но сервер сейчас не смог извлечь/проанализировать кадры.\n"
                    "Пришли 2–3 таймкода + что хотел сделать — текстовый VOD-разбор останется доступен."
                ),
            )
            return True
        except VODError as exc:
            log.warning("vod analysis failed chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "🎬 VOD-анализ временно не завершился. Видео не сохранялось. Попробуй короткий MP4-клип ещё раз.",
            )
            return True
        except Exception as exc:
            log.exception("vod ingress crashed chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "🎬 VOD временно недоступен. Видео не сохранялось; попробуй ещё раз позже.",
            )
            return True

        report = self.vod.format_report(result)

        try:
            if self.store is not None:
                self.store.add(chat_id, "user", f"[VOD media] {note or 'gameplay clip'}")
                self.store.add(chat_id, "assistant", report)
        except Exception:
            pass

        if self.player_memory is not None:
            try:
                self.player_memory.observe_vod(
                    chat_id=chat_id,
                    profile=dict(profile or {}),
                    result=result,
                    trusted=True,
                )
            except Exception as exc:
                log.warning("vod memory write failed chat_id=%s error=%s", chat_id, type(exc).__name__)

        await self.tg.send_message(chat_id, report)
        return True
