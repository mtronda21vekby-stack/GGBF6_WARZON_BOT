# -*- coding: utf-8 -*-
from __future__ import annotations

from contextvars import ContextVar

from app.i18n import normalize_locale
from app.adapters.telegram.client import TelegramClient
from app.services.voice.telegram import VoiceTelegramController

_voice_locale: ContextVar[str] = ContextVar("bco_voice_locale", default="en")
_ORIGINAL_SPEAK = VoiceTelegramController._speak
_ORIGINAL_SEND_VOICE = TelegramClient.send_voice_file


async def _localized_speak(self, chat_id, text, *, explicit, input_mode="text"):
    try:
        profile = self._profile(chat_id)
        locale = normalize_locale(profile.get("language_override") or profile.get("language") or "en")
    except Exception:
        locale = "en"
    token = _voice_locale.set(locale)
    try:
        return await _ORIGINAL_SPEAK(self, chat_id, text, explicit=explicit, input_mode=input_mode)
    finally:
        _voice_locale.reset(token)


async def _localized_send_voice(self, chat_id, file_path, caption=None, reply_markup=None):
    if caption == "Синтетический AI-голос · BLACK CROWN OPS" and _voice_locale.get() == "en":
        caption = "Synthetic AI voice · BLACK CROWN OPS"
    return await _ORIGINAL_SEND_VOICE(self, chat_id, file_path, caption=caption, reply_markup=reply_markup)


def install() -> None:
    if getattr(VoiceTelegramController, "_bco_i18n_v38", False):
        return
    VoiceTelegramController._speak = _localized_speak
    VoiceTelegramController._bco_i18n_v38 = True
    TelegramClient.send_voice_file = _localized_send_voice
