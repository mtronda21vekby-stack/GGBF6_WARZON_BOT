# app/ui/quickbar.py  (ЗАМЕНИ ЦЕЛИКОМ)
from __future__ import annotations


def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "📋 Меню"}, {"text": "⚙️ Настройки"}],
            [{"text": "🎮 Игра"}, {"text": "🎭 Режим"}, {"text": "🧠 ИИ"}],
            [{"text": "🎯 Тренировка"}, {"text": "🧟 Zombies"}, {"text": "🎬 VOD"}],
            [{"text": "👤 Профиль"}, {"text": "📡 Статус"}, {"text": "🆘 Помощь"}],
            [{"text": "🧠 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию/смерть — я дам разбор и план…",
    }


def kb_settings() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Warzone"}, {"text": "🎮 BF6"}, {"text": "🎮 BO7"}],
            [{"text": "💻 ПК (KBM)"}, {"text": "🎮 PlayStation"}, {"text": "🎮 Xbox"}],
            [{"text": "🙂 Обычный"}, {"text": "🔥 Профи"}, {"text": "😈 Демон"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери игру/устройство/режим…",
    }


def kb_game() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Warzone"}, {"text": "🎮 BF6"}, {"text": "🎮 BO7"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_mode() -> dict:
    return {
        "keyboard": [
            [{"text": "🙂 Обычный"}, {"text": "🔥 Профи"}, {"text": "😈 Демон"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


def kb_ai() -> dict:
    return {
        "keyboard": [
            [{"text": "🧠 ИИ: ВКЛ"}, {"text": "🧠 ИИ: ВЫКЛ"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }
