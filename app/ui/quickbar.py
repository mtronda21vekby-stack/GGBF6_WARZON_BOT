# app/ui/quickbar.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict


# =========================
# PREMIUM MAIN QUICKBAR
# =========================
def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "⚙️ Настройки"}, {"text": "🪖 Класс"}],
            [{"text": "🧠 ИИ"}, {"text": "🎯 Тренировка"}, {"text": "🎬 VOD"}],
            [{"text": "🧟 Zombies"}, {"text": "📌 Профиль"}, {"text": "📊 Статус"}],
            [{"text": "💎 Premium"}, {"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Опиши ситуацию — разбор как от тиммейта…",
    }


# =========================
# SETTINGS ROOT
# =========================
def kb_settings() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Выбрать игру"}],
            [{"text": "🖥 Платформа"}, {"text": "⌨️ Input"}],
            [{"text": "😈 Режим мышления"}],
            [{"text": "🧩 Настройки игры"}],  # пер-игровые настройки
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
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
    }


# =========================
# DIFFICULTY / MODE
# =========================
def kb_difficulty() -> dict:
    return {
        "keyboard": [
            [{"text": "🧠 Normal"}, {"text": "🔥 Pro"}, {"text": "😈 Demon"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


# =========================
# BF6 CLASSES
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
    }


# =========================
# WZ/BO7 ROLES (не режем)
# =========================
def kb_roles() -> dict:
    # универсальные роли для CoD режимов
    return {
        "keyboard": [
            [{"text": "⚔️ Slayer"}, {"text": "🚪 Entry"}],
            [{"text": "🧠 IGL"}, {"text": "🛡 Support"}],
            [{"text": "🌀 Flex"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


# =========================
# GAME SETTINGS MENU (per world)
# =========================
def kb_game_settings_menu(game: str) -> dict:
    g = (game or "Warzone").strip()

    # BF6 — отдельное меню с классом и тюнингами
    if g == "BF6":
        return {
            "keyboard": [
                [{"text": "🪖 BF6: Class Settings"}],
                [{"text": "🎯 BF6: Aim/Sens"}],
                [{"text": "🎮 BF6: Controller Tuning"}, {"text": "⌨️ BF6: KBM Tuning"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
        }

    # Warzone / BO7 — устройство-зависимые пакеты
    return {
        "keyboard": [
            [{"text": f"🎯 {g}: Aim/Sens"}],
            [{"text": f"🎮 {g}: Controller Tuning"}, {"text": f"⌨️ {g}: KBM Tuning"}],
            [{"text": f"🧠 {g}: Movement/Positioning"}],
            [{"text": f"🎧 {g}: Audio/Visual"}],
            [{"text": f"🎭 {g}: Role Setup"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }
