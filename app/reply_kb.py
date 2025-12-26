# -*- coding: utf-8 -*-
from typing import Dict, Any

BTN_HOME = "🏠 Главная"
BTN_MORE = "📦 Ещё"
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
BTN_DEVICE = "🎛 Настройки (девайс)"

# BF6
BTN_BF6_ROLES = "🎯 BF6 Роли"
BTN_BF6_DEATHS = "📊 BF6 Почему я умираю"
BTN_BF6_THINK = "🧠 BF6 Мышление"

BTN_SETTINGS = "⚙️ Настройки"
BTN_STATUS = "🧾 Статус"
BTN_AI = "🤖 ИИ"
BTN_HELP = "❓ Помощь"
BTN_CLEAR_MEM = "🧽 Очистить память"
BTN_RESET = "🧨 Сброс"


def _b(text: str) -> Dict[str, Any]:
    return {"text": text}


def reply_kb(profile: dict, ai_enabled: bool) -> Dict[str, Any]:
    page = (profile or {}).get("rk_page", "main")
    game = (profile or {}).get("game", "auto")

    mode = (profile or {}).get("mode", "chat")
    speed = (profile or {}).get("speed", "normal")
    memory = (profile or {}).get("memory", "on")

    mode_txt = f"{BTN_MODE}: {'CHAT' if mode=='chat' else 'COACH'}"
    lightning_txt = f"{BTN_LIGHTNING}: {'ВКЛ' if speed=='lightning' else 'ВЫКЛ'}"
    mem_txt = f"{BTN_MEMORY}: {'ВКЛ' if memory=='on' else 'ВЫКЛ'}"
    ai_txt = f"{BTN_AI}: {'ON' if ai_enabled else 'OFF'}"

    if page == "more":
        keyboard = [
            [_b(BTN_BACK), _b(BTN_HOME)],
            [_b(BTN_SETTINGS), _b(BTN_STATUS)],
            [_b(BTN_HELP), _b(ai_txt)],
            [_b(BTN_CLEAR_MEM), _b(BTN_RESET)],
        ]
    else:
        # 🎮 Главный экран
        rows = [
            [_b(BTN_GAME), _b(mode_txt)],
            [_b(lightning_txt), _b(mem_txt)],
        ]

        # BF6 — отдельный красивый блок
        if game == "bf6":
            rows += [
                [_b(BTN_BF6_ROLES), _b(BTN_BF6_DEATHS)],
                [_b(BTN_BF6_THINK), _b(BTN_DEVICE)],
            ]
        else:
            rows += [
                [_b(BTN_ZOMBIES), _b(BTN_TRAINING)],
                [_b(BTN_DAILY), _b(BTN_DEVICE)],
            ]

        rows += [[_b(BTN_PROFILE), _b(BTN_MORE)]]
        keyboard = rows

    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию или жми кнопки 👇",
    }
