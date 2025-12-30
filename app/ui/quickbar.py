# app/ui/quickbar.py
# -*- coding: utf-8 -*-
from __future__ import annotations


# =========================
# PREMIUM MAIN QUICKBAR (нижняя клавиатура)
# =========================
def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "⚙️ Настройки"}, {"text": "🎭 Роль/Класс"}],
            [{"text": "🧠 ИИ"}, {"text": "🎯 Тренировка"}, {"text": "🎬 VOD"}],
            [{"text": "🧟 Zombies"}, {"text": "📌 Профиль"}, {"text": "📊 Статус"}],
            [{"text": "💎 Premium"}, {"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,  # premium feel: закрепляем снизу
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию/смерть одной строкой — разбор как от тиммейта…",
    }


# =========================
# PREMIUM HUB (быстрые функции)
# =========================
def kb_premium() -> dict:
    return {
        "keyboard": [
            [{"text": "🎙 Голос: Тиммейт/Коуч"}],
            [{"text": "😈 Режим мышления"}, {"text": "🧩 Настройки игры"}],
            [{"text": "🎯 Тренировка: План"}, {"text": "🎬 VOD: Разбор"}],
            [{"text": "🧠 Память: Статус"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Premium-панель…",
    }


# =========================
# VOICE MODE (TEAMMATE/COACH)
# =========================
def kb_voice() -> dict:
    return {
        "keyboard": [
            [{"text": "🤝 Тиммейт"}, {"text": "📚 Коуч"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери стиль общения…",
    }


# =========================
# SETTINGS ROOT (контейнер)
# =========================
def kb_settings() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Выбрать игру"}],
            [{"text": "🖥 Платформа"}, {"text": "⌨️ Input"}],
            [{"text": "😈 Режим мышления"}],
            [{"text": "🧩 Настройки игры"}],  # per-world settings menu
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери пункт настроек…",
    }


# =========================
# GAMES
# =========================
def kb_games() -> dict:
    return {
        "keyboard": [
            [{"text": "🔥 Warzone"}, {"text": "💣 BO7"}],
            [{"text": "🪖 BF6"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


# =========================
# PLATFORM
# =========================
def kb_platform() -> dict:
    return {
        "keyboard": [
            [{"text": "🖥 PC"}, {"text": "🎮 PlayStation"}, {"text": "🎮 Xbox"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


# =========================
# INPUT
# =========================
def kb_input() -> dict:
    return {
        "keyboard": [
            [{"text": "⌨️ KBM"}, {"text": "🎮 Controller"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


# =========================
# DIFFICULTY / BRAIN MODE
# =========================
def kb_difficulty() -> dict:
    return {
        "keyboard": [
            [{"text": "🧠 Normal"}, {"text": "🔥 Pro"}, {"text": "😈 Demon"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


# =========================
# BF6 CLASSES (EN)
# =========================
def kb_bf6_classes() -> dict:
    return {
        "keyboard": [
            [{"text": "🟥 Assault"}, {"text": "🟦 Recon"}],
            [{"text": "🟨 Engineer"}, {"text": "🟩 Medic"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


# =========================
# ROLES (Warzone/BO7) (RU labels -> values inside profile EN)
# =========================
def kb_roles() -> dict:
    return {
        "keyboard": [
            [{"text": "⚔️ Слэйер"}, {"text": "🚪 Энтри"}, {"text": "🧠 IGL"}],
            [{"text": "🛡 Саппорт"}, {"text": "🌀 Флекс"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


# =========================
# PER-WORLD GAME SETTINGS MENU
# game = "Warzone" / "BO7" / "BF6"
# Требование: у BF6 настройки на EN, у Warzone/BO7 — RU.
# =========================
def kb_game_settings_menu(game: str) -> dict:
    g = (game or "Warzone").strip()
    g_up = g.upper()

    if g_up == "BF6":
        return {
            "keyboard": [
                [{"text": "🪖 BF6: Class Settings"}],
                [{"text": "🎯 BF6: Aim/Sens"}],
                [{"text": "🎮 BF6: Controller Tuning"}, {"text": "⌨️ BF6: KBM Tuning"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "one_time_keyboard": False,
            "input_field_placeholder": "BF6 settings (EN)…",
        }

    if g_up == "BO7":
        return {
            "keyboard": [
                [{"text": "🎭 BO7: Роль"}],
                [{"text": "🎯 BO7: Aim/Sens"}],
                [{"text": "🎮 BO7: Controller"}, {"text": "⌨️ BO7: KBM"}],
                [{"text": "🧠 BO7: Мувмент/Позиционка"}, {"text": "🎧 BO7: Аудио/Видео"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "one_time_keyboard": False,
            "input_field_placeholder": "Настройки BO7…",
        }

    # default Warzone
    return {
        "keyboard": [
            [{"text": "🎭 Warzone: Роль"}],
            [{"text": "🎯 Warzone: Aim/Sens"}],
            [{"text": "🎮 Warzone: Controller"}, {"text": "⌨️ Warzone: KBM"}],
            [{"text": "🧠 Warzone: Мувмент/Позиционка"}, {"text": "🎧 Warzone: Аудио/Видео"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Настройки Warzone…",
    }
