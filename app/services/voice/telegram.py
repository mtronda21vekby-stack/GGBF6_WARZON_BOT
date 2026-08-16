# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from app.services.voice.service import TTSMode, VoiceService, normalize_tts_mode
from app.ui.voice_kb import kb_voice_panel

log = logging.getLogger("bco.voice")

_MODE_BUTTONS = {
    "🔇 Voice OFF": TTSMode.OFF,
    "🔊 Voice AUTO": TTSMode.AUTO,
    "🎧 Voice ON-DEMAND": TTSMode.ON_DEMAND,
}
_OPEN_BUTTONS = {"🎙 Голос: Тиммейт/Коуч", "🔊 Озвучка", "/voice"}
_SPEAK_BUTTONS = {"🔊 Озвучить ответ", "/speak"}


def _message(raw: dict) -> dict:
    msg = raw.get("message") or raw.get("edited_message") or {}
    return msg if isinstance(msg, dict) else {}


def _chat_id_text(raw: dict) -> tuple[int | None, str]:
    msg = _message(raw)
    chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
    try:
        chat_id = int(chat.get("id"))
    except Exception:
        chat_id = None
    return chat_id, str(msg.get("text") or "").strip()


def _last_assistant(history: list[dict]) -> str:
    for item in reversed(history or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or "").lower() == "assistant":
            text = str(item.get("content") or "").strip()
            if text:
                return text
    return ""


def _signature(history: list[dict]) -> str:
    text = _last_assistant(history)
    payload = f"{len(history or [])}:{text}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class VoiceTelegramController:
    tg: Any
    profiles: Any
    store: Any
    voice: VoiceService
    usage_guard: Any = None

    def _profile(self, chat_id: int) -> dict:
        try:
            return dict(self.profiles.get(chat_id) or {})
        except Exception:
            return {}

    def _history(self, chat_id: int) -> list[dict]:
        try:
            return list(self.store.get(chat_id) or [])
        except Exception:
            return []

    def history_signature(self, chat_id: int | None) -> str:
        if chat_id is None:
            return ""
        return _signature(self._history(chat_id))

    async def _send_panel(self, chat_id: int, prefix: str = "") -> None:
        profile = self._profile(chat_id)
        mode = normalize_tts_mode(profile.get("tts_mode"))
        state = {
            TTSMode.OFF: "OFF — только текст",
            TTSMode.AUTO: "AUTO — текст + voice после AI-ответа",
            TTSMode.ON_DEMAND: "ON-DEMAND — voice только по кнопке",
        }[mode]
        body = (prefix + "\n\n" if prefix else "") + (
            "🔊 BLACK CROWN VOICE\n"
            f"Режим: {state}\n\n"
            "Текст всегда остаётся основным ответом. Голос — дополнительный канал."
        )
        await self.tg.send_message(chat_id, body, kb_voice_panel())

    async def _speak(self, chat_id: int, text: str, *, explicit: bool) -> bool:
        if self.usage_guard is not None:
            try:
                decision = self.usage_guard.check(chat_id, "voice")
                if not bool(getattr(decision, "allowed", True)):
                    if explicit:
                        wait = max(1, int(getattr(decision, "retry_after_s", 1) or 1))
                        await self._send_panel(
                            chat_id,
                            f"⏳ Озвучка на cooldown. Повтори примерно через {wait} сек.",
                        )
                    return False
            except Exception:
                pass

        profile = self._profile(chat_id)
        try:
            artifact = await self.voice.synthesize(text, profile)
            try:
                await self.tg.send_voice_file(chat_id, str(artifact.path))
            finally:
                artifact.cleanup()
            return True
        except Exception as exc:
            log.warning("voice synthesis failed chat_id=%s error=%s", chat_id, type(exc).__name__)
            if explicit:
                await self._send_panel(
                    chat_id,
                    "⚠️ Озвучка сейчас недоступна. Текстовый бот продолжает работать без ограничений.",
                )
            return False

    async def maybe_handle_command(self, raw: dict) -> bool:
        chat_id, text = _chat_id_text(raw)
        if chat_id is None or not text:
            return False

        if text in _OPEN_BUTTONS:
            await self._send_panel(chat_id)
            return True

        if text in _MODE_BUTTONS:
            mode = _MODE_BUTTONS[text]
            try:
                self.profiles.patch(chat_id, {"tts_mode": mode.value})
            except Exception:
                pass
            await self._send_panel(chat_id, f"✅ Voice mode = {mode.value}")
            return True

        if text in _SPEAK_BUTTONS:
            profile = self._profile(chat_id)
            mode = normalize_tts_mode(profile.get("tts_mode"))
            if mode == TTSMode.OFF:
                await self._send_panel(chat_id, "Сначала выбери AUTO или ON-DEMAND.")
                return True
            last = _last_assistant(self._history(chat_id))
            if not last:
                await self._send_panel(chat_id, "Пока нет AI-ответа, который можно озвучить.")
                return True
            await self._speak(chat_id, last, explicit=True)
            return True

        return False

    async def maybe_auto(self, chat_id: int | None, before_signature: str) -> bool:
        if chat_id is None:
            return False
        profile = self._profile(chat_id)
        if not self.voice.should_auto(profile):
            return False
        history = self._history(chat_id)
        after = _signature(history)
        if not after or after == before_signature:
            return False
        last = _last_assistant(history)
        if not last:
            return False
        return await self._speak(chat_id, last, explicit=False)

    @staticmethod
    def extract_chat_id(raw: dict) -> int | None:
        return _chat_id_text(raw)[0]
