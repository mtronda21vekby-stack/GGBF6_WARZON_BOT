# -*- coding: utf-8 -*-
from typing import Dict, Any

def premium_reply_kb() -> Dict[str, Any]:
    # ReplyKeyboard (не inline) — работает в группах/личке без callback
    return {
        "keyboard": [
            [{"text": "📋 Меню"}, {"text": "⚙️ Настройки"}],
            [{"text": "🎮 Игра"}, {"text": "🎭 Стиль"}, {"text": "🗣 Ответ"}],
            [{"text": "🧟 Zombies"}, {"text": "🎯 Задание дня"}, {"text": "🎬 VOD"}],
            [{"text": "👤 Профиль"}, {"text": "📡 Статус"}, {"text": "🆘 Помощь"}],
            [{"text": "🧽 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "selective": False,
    }