# -*- coding: utf-8 -*-
from typing import Dict, Any

BTN_HOME = "🏠 Главная"
BTN_MORE = "➡️ Ещё"
BTN_BACK = "⬅️ Назад"

BTN_GAME = "🎮 Игра"
BTN_MODE = "🔁 Режим"
BTN_LIGHTNING = "⚡ Молния"
BTN_MEMORY = "🧠 Память"

BTN_ZOMBIES = "🧟 Zombies"
BTN_TRAINING = "💪 Тренировка"
BTN_DAILY = "🎯 Задание дня"
BTN_VOD = "📼 VOD"
BTN_PROFILE = "📊 Профиль"
BTN_PRO = "🎮 PRO"

# ✅ Новое: настройки девайсов
BTN_DEVICE = "🎮 Настройки"

BTN_FINE = "✨ Тонкая настройка"
BTN_SETTINGS = "⚙️ Настройки"
BTN_CLEAR_MEM = "🧽 Очистить память"
BTN_RESET = "🧨 Сброс"
BTN_STATUS = "ℹ️ Статус"
BTN_AI = "🤖 ИИ"
BTN_HELP = "📎 Помощь"


def _row(*buttons: str):
    return list(buttons)


def reply_kb(profile: dict, ai_enabled: bool) -> Dict[str, Any]:
    page = (profile.get("rk_page") or "main").lower()
    if page not in ("main", "more"):
        page = "main"

    game = (profile.get("game") or "auto").upper()
    mode = (profile.get("mode") or "chat").upper()
    lightning = "ВКЛ" if profile.get("speed", "normal") == "lightning" else "ВЫКЛ"
    mem_on = (profile.get("memory", "on") == "on")
    mem = "ВКЛ" if mem_on else "ВЫКЛ"
    ai = "ON" if ai_enabled else "OFF"

    if page == "main":
        keyboard = [
            _row(f"{BTN_GAME}: {game}", f"{BTN_MODE}: {mode}"),
            _row(f"{BTN_LIGHTNING}: {lightning}", f"{BTN_MEMORY}: {mem}"),
            _row(BTN_DEVICE, BTN_PRO),
            _row(BTN_ZOMBIES, BTN_TRAINING),
            _row(BTN_DAILY, BTN_VOD),
            _row(BTN_PROFILE, BTN_FINE),
            _row(BTN_MORE),
        ]
    else:
        keyboard = [
            _row(BTN_STATUS, f"{BTN_AI}: {ai}"),
            _row(BTN_SETTINGS, BTN_HELP),
            _row(BTN_CLEAR_MEM, BTN_RESET),
            _row(BTN_HOME, BTN_BACK),
        ]

    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "is_persistent": True,
        "selective": False,
    }
