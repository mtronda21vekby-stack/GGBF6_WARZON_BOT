# -*- coding: utf-8 -*-
from typing import Dict, Any, List

def premium_reply_kb() -> Dict[str, Any]:
    """
    ReplyKeyboardMarkup (кнопки снизу). Без inline.
    """
    rows: List[List[Dict[str, str]]] = [
        [{"text": "📋 Меню"}, {"text": "⚙️ Настройки"}],
        [{"text": "🎮 Игра"}, {"text": "🎭 Стиль"}, {"text": "🗣 Ответ"}],
        [{"text": "🧟 Zombies"}, {"text": "🎯 Задание дня"}, {"text": "🎬 VOD"}],
        [{"text": "👤 Профиль"}, {"text": "📡 Статус"}, {"text": "🆘 Помощь"}],
        [{"text": "🧽 Очистить память"}, {"text": "🧨 Сброс"}],
    ]
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "is_persistent": True,
        "input_field_placeholder": "Опиши ситуацию/смерть…",
        "selective": False,
    }