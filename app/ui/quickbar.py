# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_main() -> dict:
    """
    ГЛАВНОЕ МЕНЮ (ПРЕМИУМ-ЛОГИКА)
    """
    return {
        "keyboard": [
            # --- БОЙ / ИГРА ---
            [{"text": "🎮 Игра"}, {"text": "🎯 Тренировка"}, {"text": "🧟 Zombies"}],

            # --- АНАЛИЗ / ИНТЕЛЛЕКТ ---
            [{"text": "🧠 ИИ"}, {"text": "🎬 VOD"}, {"text": "📊 Статус"}],

            # --- ПРОФИЛЬ / НАСТРОЙКИ ---
            [{"text": "📌 Профиль"}, {"text": "⚙️ Настройки"}],

            # --- СЕРВИС ---
            [{"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию или смерть — дам точный разбор…",
    }


def kb_games() -> dict:
    """
    ВЫБОР ИГРЫ
    """
    return {
        "keyboard": [
            [{"text": "🔥 Warzone"}, {"text": "🪖 BF6"}, {"text": "💣 BO7"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_training() -> dict:
    """
    ТРЕНИРОВКИ
    """
    return {
        "keyboard": [
            [{"text": "⏱ 15 мин"}, {"text": "⏱ 30 мин"}, {"text": "⏱ 60 мин"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_settings() -> dict:
    """
    НАСТРОЙКИ ПРОФИЛЯ
    """
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


def kb_profile() -> dict:
    """
    ПРОФИЛЬ (ГОТОВО ПОД PREMIUM)
    """
    return {
        "keyboard": [
            [{"text": "📈 Статистика"}, {"text": "🎯 Цели"}],
            [{"text": "🏆 Достижения"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }
