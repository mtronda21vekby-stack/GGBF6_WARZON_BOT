# -*- coding: utf-8 -*-
from typing import Dict, Any

def reply_kb_main() -> Dict[str, Any]:
    """
    Кнопки снизу (ReplyKeyboardMarkup).
    Работают в любом состоянии: как быстрые команды.
    """
    return {
        "keyboard": [
            [{"text": "📋 Меню"}, {"text": "⚙️ Настройки"}],
            [{"text": "🎮 Warzone"}, {"text": "🎮 BF6"}, {"text": "🎮 BO7"}],
            [{"text": "🧟 Zombies"}, {"text": "🎯 Daily"}],
            [{"text": "👤 Профиль"}, {"text": "🧽 Память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }
