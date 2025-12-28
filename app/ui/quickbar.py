# app/ui/quickbar.py  (ЗАМЕНИ ЦЕЛИКОМ)
from __future__ import annotations


def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "⚙️ Настройки"}, {"text": "📌 Профиль"}],
            [{"text": "🎯 Тренировка"}, {"text": "🧠 ИИ"}, {"text": "🧟 Zombies"}],
            [{"text": "🎬 VOD"}, {"text": "🆘 Помощь"}, {"text": "📡 Статус"}],
            [{"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши смерть/ситуацию — дам разбор и план…",
    }


def kb_settings() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра: Warzone"}, {"text": "🎮 Игра: BF6"}, {"text": "🎮 Игра: BO7"}],
            [{"text": "🖥 Input: KBM"}, {"text": "🎮 Input: Controller"}],
            [{"text": "🧠 Сложность: Normal"}, {"text": "🔥 Сложность: Pro"}, {"text": "😈 Сложность: Demon"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Настройки профиля…",
    }
