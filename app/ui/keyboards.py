from __future__ import annotations


# Telegram ReplyKeyboardMarkup (в виде dict для sendMessage)
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
            [{"text": "🧠 Память: ON"}, {"text": "🧠 Память: OFF"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Настройки профиля…",
    }


def kb_ai() -> dict:
    return {
        "keyboard": [
            [{"text": "🧠 ИИ: ON"}, {"text": "🧠 ИИ: OFF"}],
            [{"text": "🧠 Режим: Coach"}, {"text": "😈 Режим: DemonCoach"}],
            [{"text": "📌 Мой план"}, {"text": "🧾 Мой статус"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Напиши проблему: aim / movement / позиционка…",
    }


def kb_train() -> dict:
    return {
        "keyboard": [
            [{"text": "🎯 Aim"}, {"text": "🏃 Movement"}, {"text": "🧠 Positioning"}],
            [{"text": "⏱ 15 минут"}, {"text": "⏱ 30 минут"}, {"text": "⏱ 60 минут"}],
            [{"text": "📌 План на сегодня"}, {"text": "📈 Прогресс"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери тренировку или напиши что болит…",
    }


def kb_more() -> dict:
    return {
        "keyboard": [
            [{"text": "🎬 VOD: загрузить"}, {"text": "🎬 VOD: разбор"}],
            [{"text": "📌 Профиль"}, {"text": "🧾 Мой статус"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }
