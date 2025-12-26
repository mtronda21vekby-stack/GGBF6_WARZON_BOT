# -*- coding: utf-8 -*-
"""
BO7 MODULE (ReplyKeyboard)
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
        [{"text": "⬅️ Назад в главное"}],
    ])


def device_keyboard() -> Dict[str, Any]:
    return _kb([
        [{"text": "🎮 PS5/Xbox (Controller)"}, {"text": "🖥 PC (MnK)"}],
        [{"text": "⬅️ Назад (BO7)"}],
    ])


def handle_text(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    p = ensure_profile(chat_id)
    page = p.get("page", "main")
    t = (text or "").strip()

    if page not in ("bo7_home", "bo7_device"):
        return None

    if page == "bo7_home":
        if t == "⚙️ Настройки (Device)":
            p["page"] = "bo7_device"
            return {
                "text": "⚙️ BO7 — выбери устройство:",
                "reply_markup": device_keyboard(),
                "set_profile": {"page": "bo7_device"},
            }

        if t == "🎯 Тренировка (скоро)":
            return {
                "text": "🎯 BO7 — тренировки расширим отдельным разделом (нарастим жирок 😈).",
                "reply_markup": home_keyboard(),
            }

        if t == "⬅️ Назад в главное":
            p["page"] = "main"
            return {
                "text": "⬅️ Ок, вернул в главное меню.",
                "reply_markup": {"remove_keyboard": True},
                "set_profile": {"page": "main"},
            }

        return {"text": "BO7 модуль: жми кнопки снизу 👇", "reply_markup": home_keyboard()}

    if page == "bo7_device":
        if t == "🎮 PS5/Xbox (Controller)":
            return {"text": pro_get_text("bo7:pad"), "reply_markup": device_keyboard()}
        if t == "🖥 PC (MnK)":
            return {"text": pro_get_text("bo7:mnk"), "reply_markup": device_keyboard()}
        if t == "⬅️ Назад (BO7)":
            p["page"] = "bo7_home"
            return {
                "text": "🎮 BO7 — раздел:",
                "reply_markup": home_keyboard(),
                "set_profile": {"page": "bo7_home"},
            }
        return {"text": "Выбери устройство кнопкой 👇", "reply_markup": device_keyboard()}

    return None
