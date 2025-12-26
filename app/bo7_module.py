# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional

from app.pro_settings import get_text as pro_get_text


def bo7_menu_hub() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "⚙️ Настройки (девайс)", "callback_data": "bo7:settings"}],
        [{"text": "🧙 Pro / Расширенные", "callback_data": "bo7:pro"}],
        [{"text": "🎮 Режимы / Темп", "callback_data": "bo7:modes"}],
        [{"text": "🧠 Мышление", "callback_data": "bo7:mindset"}],
        [{"text": "⬅️ Назад", "callback_data": "nav:settings_game"}],
    ]}


def bo7_menu_device() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🎮 PS5 / Xbox (Controller)", "callback_data": "bo7:dev:pad"}],
        [{"text": "🖥 PC (Mouse & Keyboard)", "callback_data": "bo7:dev:mnk"}],
        [{"text": "⬅️ Назад", "callback_data": "bo7:hub"}],
    ]}


def _bo7_hub_text() -> str:
    return (
        "🎮 BO7 — HUB\n\n"
        "Разделы:\n"
        "• Настройки (девайс)\n"
        "• Pro / Расширенные\n"
        "• Режимы / Темп\n"
        "• Мышление\n"
    )


def _bo7_pro_text() -> str:
    return (
        "🧙 BO7 — Pro / Расширенные\n\n"
        "Выбери профиль:\n"
        "• Быстрый темп\n"
        "• Точный контроль\n"
        "• Универсал\n"
    )


def bo7_menu_pro_profiles() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "⚡ Быстрый темп", "callback_data": "bo7:pro:fast"}],
        [{"text": "🎯 Точный контроль", "callback_data": "bo7:pro:aim"}],
        [{"text": "⚖️ Универсал", "callback_data": "bo7:pro:universal"}],
        [{"text": "⬅️ Назад", "callback_data": "bo7:hub"}],
    ]}


def _bo7_profile_text(p: str) -> str:
    if p == "fast":
        return (
            "⚡ BO7 — Pro: Быстрый темп\n\n"
            "• игра от темпа, но без бесплатных смертей\n"
            "• первый контакт → репозиция\n"
            "• вход только с инфо\n"
        )
    if p == "aim":
        return (
            "🎯 BO7 — Pro: Точный контроль\n\n"
            "• ниже сенса, выше стабильность\n"
            "• дисциплина выхода\n"
            "• меньше хаоса — больше попаданий\n"
        )
    return (
        "⚖️ BO7 — Pro: Универсал\n\n"
        "• баланс темпа и стабильности\n"
        "• основа: инфо → тайминг → ресурс\n"
    )


def _bo7_modes_text() -> str:
    return (
        "🎮 BO7 — Режимы / Темп\n\n"
        "Выбери что играешь чаще:\n"
        "• соло\n"
        "• дуо\n"
        "• сквад\n\n"
        "Скажи режим — дам правила по позициям/таймингам."
    )


def _bo7_mindset_text() -> str:
    return (
        "🧠 BO7 — Мышление\n\n"
        "• всегда играй от инфо\n"
        "• после контакта — ресет/репозиция\n"
        "• не повторяй один и тот же пик\n\n"
        "Опиши 1 смерть — разберу по шагам."
    )


def handle_callback(data: str) -> Optional[Dict[str, Any]]:
    if not data.startswith("bo7:"):
        return None

    out: Dict[str, Any] = {"set_profile": {"page": "bo7"}}

    if data == "bo7:hub":
        out.update({"text": _bo7_hub_text(), "reply_markup": bo7_menu_hub()})
        return out

    if data == "bo7:settings":
        out.update({"text": "⚙️ BO7 — выбери устройство:", "reply_markup": bo7_menu_device()})
        return out

    if data.startswith("bo7:dev:"):
        dev = data.split(":", 2)[2]
        key = f"bo7:{'pad' if dev == 'pad' else 'mnk'}"
        out.update({"text": pro_get_text(key), "reply_markup": bo7_menu_device()})
        return out

    if data == "bo7:pro":
        out.update({"text": _bo7_pro_text(), "reply_markup": bo7_menu_pro_profiles()})
        return out

    if data.startswith("bo7:pro:"):
        prof = data.split(":", 2)[2]
        out.update({"text": _bo7_profile_text(prof), "reply_markup": bo7_menu_pro_profiles()})
        return out

    if data == "bo7:modes":
        out.update({"text": _bo7_modes_text(), "reply_markup": bo7_menu_hub()})
        return out

    if data == "bo7:mindset":
        out.update({"text": _bo7_mindset_text(), "reply_markup": bo7_menu_hub()})
        return out

    out.update({"text": _bo7_hub_text(), "reply_markup": bo7_menu_hub()})
    return out
