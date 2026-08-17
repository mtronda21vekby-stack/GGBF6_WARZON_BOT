# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import logging
import secrets
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.services.voice.transcription import OpenAITranscriptionBackend, TranscriptionError, TranscriptionResult

log = logging.getLogger("bco.voice.ingress")


def _message(update: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = update.get("message") or update.get("edited_message")
    return raw if isinstance(raw, dict) else None


def _callback(update: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = update.get("callback_query")
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
    audio = message.get("audio")
    if isinstance(audio, dict) and audio.get("file_id"):
        mime = str(audio.get("mime_type") or "").casefold()
        if not mime or mime.startswith("audio/"):
            return audio
    return None


def _audio_suffix(payload: Mapping[str, Any]) -> str:
    name = str(payload.get("file_name") or "").strip().casefold()
    for suffix in (".ogg", ".oga", ".opus", ".mp3", ".m4a", ".mp4", ".wav", ".webm", ".flac"):
        if name.endswith(suffix):
            return suffix
    mime = str(payload.get("mime_type") or "").strip().casefold()
    return {
        "audio/ogg": ".ogg",
        "audio/opus": ".opus",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
        "audio/flac": ".flac",
    }.get(mime, ".ogg")


@dataclass(frozen=True)
class PendingTranscript:
    text: str
    confidence: float | None
    model: str
    duration_s: int
    expires_at: float


@dataclass
class TelegramVoiceIngress:
    tg: Any
    transcription: OpenAITranscriptionBackend
    profiles: Any = None
    usage_guard: Any = None
    enabled: bool = True
    max_bytes: int = 12 * 1024 * 1024
    max_duration_s: int = 300
    confidence_threshold: float = 0.58
    confirmation_ttl_s: int = 120
    pending: dict[tuple[int, str], PendingTranscript] = field(default_factory=dict)

    def _profile(self, chat_id: int) -> dict[str, Any]:
        if self.profiles is None:
            return {}
        getter = getattr(self.profiles, "get", None)
        if not callable(getter):
            return {}
        try:
            return dict(getter(chat_id) or {})
        except Exception:
            return {}

    def _purge_pending(self) -> None:
        now = time.monotonic()
        if len(self.pending) < 128 and all(item.expires_at > now for item in self.pending.values()):
            return
        self.pending = {key: item for key, item in self.pending.items() if item.expires_at > now}
        if len(self.pending) > 512:
            ordered = sorted(self.pending.items(), key=lambda pair: pair[1].expires_at, reverse=True)[:512]
            self.pending = dict(ordered)

    async def _ack(self, callback_id: str, text: str | None = None) -> None:
        if not callback_id:
            return
        answer = getattr(self.tg, "answer_callback_query", None)
        if not callable(answer):
            return
        try:
            await answer(callback_id, text)
        except Exception:
            pass

    def _synthetic_update(
        self,
        source: Mapping[str, Any],
        *,
        text: str,
        duration_s: int,
        confidence: float | None,
        model: str,
        confirmed: bool,
    ) -> dict[str, Any]:
        transformed = copy.deepcopy(dict(source))
        callback = _callback(transformed)
        if callback:
            callback_message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
            sender = callback.get("from") if isinstance(callback.get("from"), dict) else {}
            synthetic: dict[str, Any] = {
                "message_id": int(callback_message.get("message_id") or 0),
                "chat": dict(callback_message.get("chat") or {}),
                "from": dict(sender),
            }
            transformed.pop("callback_query", None)
            transformed["message"] = synthetic
        else:
            key = "message" if isinstance(transformed.get("message"), dict) else "edited_message"
            synthetic = dict(transformed.get(key) or {})
            synthetic.pop("voice", None)
            synthetic.pop("audio", None)
            transformed[key] = synthetic

        synthetic["text"] = str(text or "")[:12000]
        synthetic["_bco_input_mode"] = "voice_confirmed" if confirmed else "voice"
        synthetic["_bco_voice_duration_s"] = int(duration_s or 0)
        synthetic["_bco_voice_confidence"] = confidence
        synthetic["_bco_voice_model"] = str(model or "")[:80]
        return transformed

    async def _handle_confirmation_callback(self, update: Mapping[str, Any]) -> tuple[dict[str, Any], bool] | None:
        callback = _callback(update)
        if not callback:
            return None
        data = str(callback.get("data") or "").strip()
        if not data.startswith("bco:voice:"):
            return None

        message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
        chat_id = _chat_id(message)
        callback_id = str(callback.get("id") or "")
        if chat_id is None:
            await self._ack(callback_id)
            return dict(update), True

        parts = data.split(":", 3)
        if len(parts) != 4:
            await self._ack(callback_id)
            return dict(update), True
        action, nonce = parts[2], parts[3]
        self._purge_pending()
        pending = self.pending.pop((chat_id, nonce), None)
        if pending is None or pending.expires_at <= time.monotonic():
            await self._ack(callback_id, "Транскрипция уже истекла")
            await self.tg.send_message(chat_id, "🎙 Транскрипция истекла. Пришли голосовое ещё раз.")
            return dict(update), True

        if action == "discard":
            await self._ack(callback_id, "Повтори голосовое")
            await self.tg.send_message(chat_id, "🎙 Окей. Повтори голосовое — лучше ближе к микрофону и без сильного фонового шума.")
            return dict(update), True
        if action != "accept":
            await self._ack(callback_id)
            return dict(update), True

        await self._ack(callback_id, "Использую транскрипцию")
        transformed = self._synthetic_update(
            update,
            text=pending.text,
            duration_s=pending.duration_s,
            confidence=pending.confidence,
            model=pending.model,
            confirmed=True,
        )
        return transformed, True

    async def transform(self, update: Mapping[str, Any] | None) -> tuple[dict[str, Any], bool]:
        """Normalize Telegram voice/audio into the same text Intelligence Core."""
        if not self.enabled or not isinstance(update, Mapping):
            return dict(update or {}), False

        confirmation = await self._handle_confirmation_callback(update)
        if confirmation is not None:
            return confirmation

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

        suffix = _audio_suffix(voice)
        try:
            with tempfile.TemporaryDirectory(prefix="bco-stt-") as td:
                source = Path(td) / f"voice{suffix}"
                try:
                    await self.tg.download_file(
                        file_id,
                        str(source),
                        max_bytes=byte_limit,
                        timeout_s=60.0,
                    )
                except Exception as exc:
                    raise TranscriptionError("Telegram voice download failed") from exc

                rich = getattr(self.transcription, "transcribe_result", None)
                profile = self._profile(chat_id)
                if callable(rich):
                    try:
                        result = await rich(source, profile=profile)
                    except TypeError:
                        result = await rich(source)
                else:
                    transcribe = getattr(self.transcription, "transcribe")
                    try:
                        text = await transcribe(source, profile=profile)
                    except TypeError:
                        text = await transcribe(source)
                    result = TranscriptionResult(
                        text=str(text or ""),
                        confidence=None,
                        model=str(getattr(self.transcription, "model", "unknown")),
                        language="auto",
                    )
        except (ValueError, TranscriptionError) as exc:
            log.warning("voice transcription rejected chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "🎙 Не смог надёжно разобрать голосовое. Попробуй ещё раз — я поддерживаю Telegram voice, MP3, M4A, WAV и WebM.",
            )
            return dict(update), True
        except Exception as exc:
            log.exception("voice transcription crashed chat_id=%s error=%s", chat_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "🎙 Голосовой канал перезапускается. Повтори сообщение через несколько секунд; текстовый режим остаётся доступен.",
            )
            return dict(update), True

        transcript = " ".join(str(result.text or "").split()).strip()
        if len(transcript) < 2:
            await self.tg.send_message(chat_id, "🎙 В голосовом почти не было распознаваемой речи.")
            return dict(update), True

        threshold = max(0.0, min(1.0, float(self.confidence_threshold or 0.0)))
        confidence = result.confidence
        if confidence is not None and confidence < threshold:
            self._purge_pending()
            nonce = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10]
            self.pending[(chat_id, nonce)] = PendingTranscript(
                text=transcript[:12000],
                confidence=confidence,
                model=result.model,
                duration_s=duration,
                expires_at=time.monotonic() + max(30, int(self.confirmation_ttl_s or 120)),
            )
            percent = result.confidence_percent or 0
            preview = transcript[:500] + ("…" if len(transcript) > 500 else "")
            markup = {
                "inline_keyboard": [
                    [
                        {"text": "✓ USE TRANSCRIPT", "callback_data": f"bco:voice:accept:{nonce}", "style": "success"},
                        {"text": "↻ RETRY", "callback_data": f"bco:voice:discard:{nonce}", "style": "danger"},
                    ]
                ]
            }
            await self.tg.send_message(
                chat_id,
                f"🎙 Не уверен в распознавании ({percent}%).\n\nЯ услышал:\n«{preview}»\n\nПодтверди, прежде чем я использую это в анализе и памяти.",
                markup,
            )
            log.info(
                "voice transcript needs confirmation chat_id=%s confidence=%.3f chars=%s model=%s",
                chat_id,
                confidence,
                len(transcript),
                result.model,
            )
            return dict(update), True

        transformed = self._synthetic_update(
            update,
            text=transcript,
            duration_s=duration,
            confidence=confidence,
            model=result.model,
            confirmed=False,
        )
        log.info(
            "voice transcribed chat_id=%s duration_s=%s chars=%s confidence=%s model=%s fallback=%s context=%s",
            chat_id,
            duration,
            len(transcript),
            "unknown" if confidence is None else f"{confidence:.3f}",
            result.model,
            bool(result.fallback_used),
            bool(self._profile(chat_id)),
        )
        return transformed, True
