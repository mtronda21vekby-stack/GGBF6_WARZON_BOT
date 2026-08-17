# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Mapping

SUPPORTED_LOCALES = ("ru", "en")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_LATIN = re.compile(r"[A-Za-z]")


def normalize_locale(value: Any, default: str = "en") -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if raw.startswith("ru"):
        return "ru"
    if raw.startswith("en"):
        return "en"
    return default if default in SUPPORTED_LOCALES else "en"


def detect_text_locale(text: Any) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    cyr = len(_CYRILLIC.findall(value))
    lat = len(_LATIN.findall(value))
    if cyr >= 2 and cyr > lat:
        return "ru"
    if lat >= 2 and lat > cyr:
        return "en"
    return None


def telegram_user(raw: Mapping[str, Any] | None) -> Mapping[str, Any]:
    data = raw if isinstance(raw, Mapping) else {}
    callback = data.get("callback_query") if isinstance(data.get("callback_query"), Mapping) else {}
    if callback:
        user = callback.get("from")
        return user if isinstance(user, Mapping) else {}
    message = data.get("message") or data.get("edited_message") or {}
    if not isinstance(message, Mapping):
        return {}
    user = message.get("from")
    return user if isinstance(user, Mapping) else {}


def telegram_message(raw: Mapping[str, Any] | None) -> Mapping[str, Any]:
    data = raw if isinstance(raw, Mapping) else {}
    callback = data.get("callback_query") if isinstance(data.get("callback_query"), Mapping) else {}
    if callback:
        message = callback.get("message")
        return message if isinstance(message, Mapping) else {}
    message = data.get("message") or data.get("edited_message") or {}
    return message if isinstance(message, Mapping) else {}


def resolve_locale(*, raw: Mapping[str, Any] | None = None, profile: Mapping[str, Any] | None = None, text: Any = None) -> str:
    p = profile if isinstance(profile, Mapping) else {}
    override = str(p.get("language_override") or "").strip()
    if override:
        return normalize_locale(override)
    typed = detect_text_locale(text)
    if typed:
        return typed
    user = telegram_user(raw)
    if user.get("language_code"):
        return normalize_locale(user.get("language_code"))
    if p.get("language"):
        return normalize_locale(p.get("language"))
    return "en"


def tr(locale: str, ru: str, en: str) -> str:
    return ru if normalize_locale(locale) == "ru" else en
