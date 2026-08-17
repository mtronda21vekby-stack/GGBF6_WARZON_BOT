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
_VOICE_BUTTONS = {
    "🎙 CEDAR": "cedar",
    "🎙 MARIN": "marin",
}
_OPEN_BUTTONS = {"🎙 Голос: Тиммейт/Коуч", "🔊 Озвучка", "/voice"}
_SPEAK_BUTTONS = {"🔊 Озвучить ответ", "/speak"}
_TEST_BUTTONS = {"🧪 Тест голоса", "/voice_test"}
_TEST_LINE = (
    "Связь установлена. Голосовой канал работает. Я понимаю твою речь, сохраняю тактический смысл и готов отвечать как тиммейт или коуч."
)


def _message(raw: dict) -> dict:
    callback = raw.get("callback_query") or {}
    if isinstance(callback, dict) and callback:
        msg = callback.get("message") or {}
        return msg if isinstance(msg, dict) else {}
    msg = raw.get("message") or raw.get("edited_message") or {}
    return msg if isinstance(msg, dict) else {}


def _chat_id_text(raw: dict) -> tuple[int | None, str]:
    callback = raw.get("callback_query") or {}
    if isinstance(callback, dict) and callback:
        msg = callback.get("message") or {}
        text = str(callback.get("data") or "").strip()
    else:
        msg = _message(raw)
        text = str(msg.get("text") or "").strip()
    msg = msg if isinstance(msg, dict) else {}
    chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
    try:
        chat_id = int(chat.get("id"))
    except Exception:
        chat_id = None
    return chat_id, text


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

    def _voice_details(self, profile: dict) -> dict[str, Any]:
        describe = getattr(self.voice, "describe", None)
        if callable(describe):
            try:
                return dict(describe(profile) or {})
            except Exception:
                pass
        return {
            "provider": "SYNTHETIC VOICE",
            "voice": str(profile.get("tts_voice") or "CEDAR").upper(),
            "local_fallback": False,
        }

    async def _send_panel(self, chat_id: int, prefix: str = "") -> None:
        profile = self._profile(chat_id)
        mode = normalize_tts_mode(profile.get("tts_mode"))
        details = self._voice_details(profile)
        explicit_mode = bool(str(profile.get("tts_mode") or "").strip())
        follow_input = bool(getattr(self.voice, "follow_input_active", False))
        if not explicit_mode and follow_input:
            state = "SMART DUPLEX — voice→voice, text→text"
        else:
            state = {
                TTSMode.OFF: "OFF — только текст",
                TTSMode.AUTO: "AUTO — voice после каждого нового AI-ответа",
                TTSMode.ON_DEMAND: "ON-DEMAND — voice только по команде",
            }[mode]
        fallback = " · LOCAL FALLBACK READY" if details.get("local_fallback") else ""
        body = (prefix + "\n\n" if prefix else "") + (
            "🔊 BLACK CROWN VOICE\n"
            f"Режим: {state}\n"
            f"Движок: {str(details.get('provider') or 'VOICE').upper()}{fallback}\n"
            f"Голос: {str(details.get('voice') or 'CEDAR').upper()}\n\n"
            "SMART DUPLEX: если ты говоришь голосом, я отвечаю текстом и голосом. Явный Voice OFF всегда отключает это поведение.\n"
            "CEDAR — собранный тактический тембр. MARIN — более мягкая и живая подача.\n"
            "Голос синтетический и сгенерирован ИИ."
        )
        await self.tg.send_message(chat_id, body, kb_voice_panel())

    async def _chat_action(self, chat_id: int, action: str) -> None:
        sender = getattr(self.tg, "send_chat_action", None)
        if not callable(sender):
            return
        try:
            await sender(chat_id, action)
        except Exception:
            pass

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
            await self._chat_action(chat_id, "record_voice")
            artifact = await self.voice.synthesize(text, profile)
            try:
                await self._chat_action(chat_id, "upload_voice")
                caption = "Синтетический AI-голос · BLACK CROWN OPS"
                await self.tg.send_voice_file(
                    chat_id,
                    str(artifact.path),
                    caption=caption,
                )
                log.info(
                    "voice delivered chat_id=%s provider=%s voice=%s chars=%s",
                    chat_id,
                    str(getattr(artifact, "provider", "unknown"))[:24],
                    str(getattr(artifact, "voice_name", ""))[:32],
                    len(str(getattr(artifact, "spoken_text", "") or "")),
                )
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

        if text in _VOICE_BUTTONS:
            voice_name = _VOICE_BUTTONS[text]
            try:
                self.profiles.patch(chat_id, {"tts_voice": voice_name})
            except Exception:
                pass
            await self._send_panel(chat_id, f"✅ Голос переключён: {voice_name.upper()}")
            return True

        if text in _TEST_BUTTONS:
            await self._speak(chat_id, _TEST_LINE, explicit=True)
            return True

        if text in _SPEAK_BUTTONS:
            profile = self._profile(chat_id)
            mode = normalize_tts_mode(profile.get("tts_mode"))
            if mode == TTSMode.OFF and str(profile.get("tts_mode") or "").strip():
                await self._send_panel(chat_id, "Сначала выбери AUTO или ON-DEMAND.")
                return True
            last = _last_assistant(self._history(chat_id))
            if not last:
                await self._send_panel(chat_id, "Пока нет AI-ответа, который можно озвучить.")
                return True
            await self._speak(chat_id, last, explicit=True)
            return True

        return False

    async def maybe_auto(self, chat_id: int | None, before_signature: str, *, input_mode: str = "text") -> bool:
        if chat_id is None:
            return False
        profile = self._profile(chat_id)
        should_auto = getattr(self.voice, "should_auto", None)
        if not callable(should_auto):
            return False
        try:
            enabled = bool(should_auto(profile, input_mode=input_mode))
        except TypeError:
            # Backward-compatible with older adapters/tests that implement the
            # pre-v20 `should_auto(profile)` signature.
            enabled = bool(should_auto(profile))
        if not enabled:
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
