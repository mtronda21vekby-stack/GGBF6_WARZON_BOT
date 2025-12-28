def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "⚙️ Настройки"}, {"text": "📌 Профиль"}],
            [{"text": "🎯 Тренировка"}, {"text": "🧠 ИИ"}, {"text": "🧟 Zombies"}],
            [{"text": "🎬 VOD"}, {"text": "📡 Статус"}],
            [{"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_training() -> dict:
    return {
        "keyboard": [
            [{"text": "⏱ 15 мин"}, {"text": "⏱ 30 мин"}, {"text": "⏱ 60 мин"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
    }


def kb_zombies() -> dict:
    return {
        "keyboard": [
            [{"text": "🧟 Новичок"}, {"text": "🔥 Про"}, {"text": "😈 Demon"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
    }
