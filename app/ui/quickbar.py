from __future__ import annotations


def quickbar() -> dict:
    return {
        "keyboard": [
            [{"text": "📋 Меню"}, {"text": "⚙️ Настройки"}],
            [{"text": "🎮 Игра"}, {"text": "🎭 Стиль"}, {"text": "💬 Ответ"}],
            [{"text": "🧟 Zombies"}, {"text": "🎯 Задание дня"}, {"text": "🎬 VOD"}],
            [{"text": "👤 Профиль"}, {"text": "📡 Статус"}, {"text": "🆘 Помощь"}],
            [{"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию/смерть…",
    }
