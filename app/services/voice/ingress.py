# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.services.voice.transcription import OpenAITranscriptionBackend, TranscriptionError

log = logging.getLogger("bco.voice.ingress")


def _message(update: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = update.get("message") or update.get("edited_message")
    return raw if isinstance(raw, dict) else None


def _chat_id(message: Mapping[str, Any]) -> int | None:
    try:
        return int(((message.get("chat") or {}).get("id")))
    except Exception:
        return None


def _voice_payload(message: Mapping[str, Any]) -> dict[str, Any] | None:
    voice = message.get("voice")
    if isinstance(voice, dict) and voice.get("file_id"):
        return voice
    # Also accept audio clips recorded/sent as files when Telegram provides a
    # supported audio mime type. Ordinary documents are intentionally ignored.
    audio = message.get("audio")
    if isinstance(audio, dict) and audio.get("file_id"):
        mime = str(audio.get("mime_type") or "").casefold()
        if not mime or mime.startswith("audio/"):
            return audio
    return None


@dataclass
class TelegramVoiceIngress:
    tg: Any
    transcription: OpenAITranscriptionBackend
    usage_guard: Any = None
    enabled: bool = True
    max_bytes: int = 12 * 1024 * 1024
    max_duration_s: int = 300

    async def transform(self, update: Mapping[str, Any] | None) -> tuple[dict[str, Any], bool]:
        """Return `(update, transformed)`; voice becomes a normal text update."""
        if not self.enabled or not isinstance(update, Mapping):
            return dict(update or {}), False
        message = _message(update)
        if not message:
            return dict(update), False
        voice = _voice_payload(message)
        if not voice:
            return dict(update), False

        chat_id = _chat_id(message)
        if chat_id is None:
            return dict(update), False

        file_id = str(voice.get("file_id") or "").strip()
        if not file_id:
            return dict(update), False

        declared_size = int(voice.get("file_size") or 0)
        duration = int(voice.get("duration") or 0)
        byte_limit = max(256 * 1024, int(self.max_bytes or 0))
        duration_limit = max(5, int(self.max_duration_s or 0))

        if declared_size and declared_size > byte_limit:
            await self.tg.send_message(chat_id, "🎙 Голосовое слишком большое. Пришли фрагмент короче или раздели его на части.")
            return dict(update), True
        if duration and duration > duration_limit:
            await self.tg.send_message(
                chat_id,
                f"🎙 Я понимаю голосовые до {duration_limit // 60} мин за сообщение. Раздели длинное сообщение на несколько частей.",
            )
            return dict(update), True

        if self.usage_guard is not None:
            try:
                decision = self.usage_guard.check(chat_id, "voice")
                if not bool(getattr(decision, "allowed", True)):
                    wait = max(1, int(getattr(decision, "retry_after_s", 1) or 1))
                    await self.tg.send_message(chat_id, f"🎙 Голосовой ввод на cooldown. Повтори примерно через {wait} сек.")
                    return dict(update), True
            except Exception:
                pass

        try:
            await self.tg.send_chat_action(chat_id, "typing")
        except Exception:
            pass

        try:
            with tempfile.TemporaryDirectory(prefix="bco-stt-") as td:
                source = Path(td) / "voice.ogg"
                await self.tg.download_file(
                    file_id,
                    str(source),
                    max_bytes=byte_limit,
                    timeout_s=60.0,
                )
                transcript = await self.transcription.transcribe(source)
        except (ValueError, TranscriptionError) as exc:
            log.warning("voice transcription rejected chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "🎙 Не смог надёжно разобрать это голосовое. Повтори чуть короче и без сильного фонового шума.",
            )
            return dict(update), True
        except Exception as exc:
            log.exception("voice transcription crashed chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "🎙 Голосовой ввод временно недоступен. Текстовые сообщения продолжают работать.",
            )
            return dict(update), True

        transcript = " ".join(str(transcript or "").split()).strip()
        if len(transcript) < 2:
            await self.tg.send_message(chat_id, "🎙 В голосовом почти не было распознаваемой речи.")
            return dict(update), True

        transformed = copy.deepcopy(dict(update))
        key = "message" if isinstance(transformed.get("message"), dict) else "edited_message"
        synthetic = dict(transformed.get(key) or {})
        synthetic.pop("voice", None)
        synthetic.pop("audio", None)
        synthetic["text"] = transcript[:12000]
        synthetic["_bco_input_mode"] = "voice"
        synthetic["_bco_voice_duration_s"] = duration
        transformed[key] = synthetic

        log.info(
            "voice transcribed chat_id=%s duration_s=%s chars=%s model=%s",
            chat_id,
            duration,
            len(transcript),
            getattr(self.transcription, "model", "unknown"),
        )
        return transformed, True
