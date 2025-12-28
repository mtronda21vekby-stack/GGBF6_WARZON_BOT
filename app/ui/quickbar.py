# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "🎯 Тренировка"}, {"text": "🧟 Zombies"}],
            [{"text": "🧠 ИИ"}, {"text": "🎬 VOD"}, {"text": "📊 Статус"}],
            [{"text": "📌 Профиль"}, {"text": "⚙️ Настройки"}],
            [{"text": "💎 Premium"}, {"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию — ИИ разберёт как тиммейт…",
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


def kb_premium() -> dict:
    return {
        "keyboard": [
            [{"text": "💎 Что даёт Premium"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }
