# app/ui/quickbar.py
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


def kb_settings(game: str = "AUTO") -> dict:
    # BF6: только “настройки” на EN (как ты просил)
    bf6 = (game == "BF6")
    game_btns = [
        {"text": "🎮 Игра: Warzone"},
        {"text": "🎮 Игра: BF6"},
        {"text": "🎮 Игра: BO7"},
    ]
    input_btns = [
        {"text": "🖥 Input: KBM"} if bf6 else {"text": "🖥 Ввод: KBM"},
        {"text": "🎮 Input: Controller"} if bf6 else {"text": "🎮 Ввод: Controller"},
    ]
    diff_btns = [
        {"text": "🧠 Сложность: Normal"} if bf6 else {"text": "🧠 Сложность: Normal"},
        {"text": "🔥 Сложность: Pro"} if bf6 else {"text": "🔥 Сложность: Pro"},
        {"text": "😈 Сложность: Demon"} if bf6 else {"text": "😈 Сложность: Demon"},
    ]

    return {
        "keyboard": [
            game_btns,
            input_btns,
            diff_btns,
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Настройки профиля…",
    }
