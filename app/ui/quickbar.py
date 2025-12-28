# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "🎭 Роль"}, {"text": "⚙️ Настройки"}],
            [{"text": "🎯 Тренировка"}, {"text": "🧠 ИИ"}, {"text": "🎬 VOD"}],
            [{"text": "🧟 Zombies"}, {"text": "📌 Профиль"}, {"text": "📊 Статус"}],
            [{"text": "💎 Premium"}, {"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию — разбор будет как от тиммейта…",
    }


def kb_games() -> dict:
    return {
        "keyboard": [
            [{"text": "🔥 Warzone"}, {"text": "🪖 BF6"}, {"text": "💣 BO7"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_roles(game: str) -> dict:
    g = (game or "warzone").lower()

    if g == "warzone":
        rows = [
            [{"text": "🎭 Entry"}, {"text": "🎭 Anchor"}],
            [{"text": "🎭 Sniper"}],
        ]
    elif g == "bf6":
        rows = [
            [{"text": "🎭 Assault"}, {"text": "🎭 Engineer"}],
            [{"text": "🎭 Support"}, {"text": "🎭 Recon"}],
        ]
    else:  # bo7
        rows = [
            [{"text": "🎭 Slayer"}, {"text": "🎭 Anchor"}],
            [{"text": "🎭 Objective"}],
        ]

    rows.append([{"text": "⬅️ Назад"}])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


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
    }


def kb_training() -> dict:
    return {
        "keyboard": [
            [{"text": "⏱ 15 мин"}, {"text": "⏱ 30 мин"}, {"text": "⏱ 60 мин"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_ai() -> dict:
    return {
        "keyboard": [
            [{"text": "😈 Demon-анализ"}, {"text": "🔥 Pro-анализ"}],
            [{"text": "🧠 Общий разбор"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_zombies() -> dict:
    return {
        "keyboard": [
            [{"text": "🗺 Ashes"}, {"text": "🗺 Astra"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_premium() -> dict:
    return {
        "keyboard": [
            [{"text": "💎 Что даёт Premium"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_profile() -> dict:
    return {
        "keyboard": [
            [{"text": "📈 Статистика"}, {"text": "🗓 Сезон"}],
            [{"text": "♻️ Сброс сезона"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }
