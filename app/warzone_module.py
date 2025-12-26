# -*- coding: utf-8 -*-
"""
WARZONE MODULE (ReplyKeyboard)
- отдельный модуль, не конфликтует с BF6/BO7
- работает без AI, безопасно
- использует pro_settings.get_text() для девайс-настроек
"""

from typing import Dict, Any, Optional

from app.state import ensure_profile
from app.pro_settings import get_text as pro_get_text


def _kb(rows):
    return {"keyboard": rows, "resize_keyboard": True}


def home_keyboard() -> Dict[str, Any]:
    return _kb([
        [{"text": "⚙️ Настройки (Device)"}],
        [{"text": "🎯 Тренировка (скоро)"}],
        [{"text": "🎬 VOD / Разбор (скоро)"}],
        [{"text": "⬅️ Назад в главное"}],
    ])


def device_keyboard() -> Dict[str, Any]:
    return _kb([
        [{"text": "🎮 PS5/Xbox (Controller)"}, {"text": "🖥 PC (MnK)"}],
        [{"text": "⬅️ Назад (Warzone)"}],
    ])


def handle_text(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    p = ensure_profile(chat_id)
    page = p.get("page", "main")
    t = (text or "").strip()

    # работаем только если пользователь в Warzone модуле
    if page not in ("wz_home", "wz_device"):
        return None

    # ---------- WZ HOME ----------
    if page == "wz_home":
        if t == "⚙️ Настройки (Device)":
            p["page"] = "wz_device"
            return {
                "text": "⚙️ Warzone — выбери устройство:",
                "reply_markup": device_keyboard(),
                "set_profile": {"page": "wz_device"},
            }

        if t == "🎯 Тренировка (скоро)":
            return {
                "text": "🎯 Warzone — тренировки добавим следующим слоем (не удаляем ничего, только наращиваем).",
                "reply_markup": home_keyboard(),
            }

        if t == "🎬 VOD / Разбор (скоро)":
            return {
                "text": "🎬 Warzone — VOD/разбор уже есть в общем меню. Дальше сделаем отдельный Warzone-раздел.",
                "reply_markup": home_keyboard(),
            }

        if t == "⬅️ Назад в главное":
            p["page"] = "main"
            return {
                "text": "⬅️ Ок, вернул в главное меню.",
                "reply_markup": {"remove_keyboard": True},
                "set_profile": {"page": "main"},
            }

        # любой другой текст в модуле — подсказка
        return {
            "text": "Warzone модуль: жми кнопки снизу 👇",
            "reply_markup": home_keyboard(),
        }

    # ---------- WZ DEVICE ----------
    if page == "wz_device":
        if t == "🎮 PS5/Xbox (Controller)":
            return {"text": pro_get_text("wz:pad"), "reply_markup": device_keyboard()}
        if t == "🖥 PC (MnK)":
            return {"text": pro_get_text("wz:mnk"), "reply_markup": device_keyboard()}
        if t == "⬅️ Назад (Warzone)":
            p["page"] = "wz_home"
            return {
                "text": "🎮 Warzone — раздел:",
                "reply_markup": home_keyboard(),
                "set_profile": {"page": "wz_home"},
            }

        return {"text": "Выбери устройство кнопкой 👇", "reply_markup": device_keyboard()}

    return None
