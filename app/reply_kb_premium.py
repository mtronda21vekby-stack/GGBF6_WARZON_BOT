# -*- coding: utf-8 -*-
"""
Premium UI v1
• Только нижняя клавиатура (ReplyKeyboard)
• Никаких inline / верхних кнопок
• Быстро, чисто, premium UX
"""

from typing import Dict, Any, List

# =========================
# BASE BUTTON HELPERS
# =========================

def btn(text: str) -> Dict[str, str]:
    return {"text": text}


def keyboard(rows: List[List[str]], resize: bool = True) -> Dict[str, Any]:
    return {
        "keyboard": [[btn(t) for t in row] for row in rows],
        "resize_keyboard": resize,
        "one_time_keyboard": False,
        "selective": False,
    }


# =========================
# MAIN PREMIUM KEYBOARD
# =========================

def kb_main_premium() -> Dict[str, Any]:
    return keyboard([
        ["🎮 Игра", "🎭 Стиль", "🗣 Ответ"],
        ["🧠 Память", "⚡ Молния", "🤖 ИИ"],
        ["🧟 Zombies", "🎯 Задание дня"],
        ["⚙️ Настройки", "📦 Ещё"],
        ["❌ Сброс", "🆘 Помощь"],
    ])


# =========================
# GAME SELECT
# =========================

def kb_games() -> Dict[str, Any]:
    return keyboard([
        ["🎮 AUTO"],
        ["🎮 Warzone"],
        ["🎮 BF6"],
        ["🎮 BO7"],
        ["⬅️ Назад"],
    ])


# =========================
# STYLE / PERSONA
# =========================

def kb_persona() -> Dict[str, Any]:
    return keyboard([
        ["😌 Chill"],
        ["🎯 Pro"],
        ["😈 Demon"],
        ["⬅️ Назад"],
    ])


# =========================
# VERBOSITY
# =========================

def kb_verbosity() -> Dict[str, Any]:
    return keyboard([
        ["🗣 Коротко"],
        ["🗣 Нормально"],
        ["🗣 Подробно"],
        ["⬅️ Назад"],
    ])


# =========================
# SETTINGS
# =========================

def kb_settings() -> Dict[str, Any]:
    return keyboard([
        ["📡 Статус"],
        ["🎮 Настройки игр"],
        ["🧩 UI"],
        ["⬅️ Назад"],
    ])


# =========================
# BF6 DEVICES (PREP)
# =========================

def kb_bf6_device() -> Dict[str, Any]:
    return keyboard([
        ["🎮 Controller"],
        ["🖥 Mouse & Keyboard"],
        ["⬅️ Назад"],
    ])


# =========================
# MORE
# =========================

def kb_more() -> Dict[str, Any]:
    return keyboard([
        ["🎬 VOD Разбор"],
        ["👤 Профиль"],
        ["🧽 Очистить память"],
        ["⬅️ Назад"],
    ])


# =========================
# RESET / CONFIRM
# =========================

def kb_reset_confirm() -> Dict[str, Any]:
    return keyboard([
        ["✅ Да, сбросить"],
        ["❌ Отмена"],
    ])


# =========================
# HELP
# =========================

def kb_help() -> Dict[str, Any]:
    return keyboard([
        ["ℹ️ Как пользоваться"],
        ["🎯 Пример смерти"],
        ["⬅️ Назад"],
    ])