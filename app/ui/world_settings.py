# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_world_settings(game: str) -> dict:
    g = (game or "warzone").lower()

    # Warzone / BO7 — RU
    if g in ("warzone", "bo7"):
        return {
            "keyboard": [
                [{"text": "⚡ Пресет: PC"}, {"text": "⚡ Пресет: PS"}, {"text": "⚡ Пресет: Xbox"}],
                [{"text": "🎯 Чувствительность"}, {"text": "🖼 FOV"}, {"text": "🎮 Аим/Стик"}],
                [{"text": "🔊 Аудио"}, {"text": "🎥 Графика"}, {"text": "🧠 Геймплей"}],
                [{"text": "📄 Показать мои настройки"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
        }

    # BF6 — EN (settings labels)
    return {
        "keyboard": [
            [{"text": "⚡ Preset: PC"}, {"text": "⚡ Preset: PS"}, {"text": "⚡ Preset: Xbox"}],
            [{"text": "🎯 Sensitivity"}, {"text": "🖼 FOV"}, {"text": "🎮 Aim/Stick"}],
            [{"text": "🔊 Audio"}, {"text": "🎥 Graphics"}, {"text": "🧠 Gameplay"}],
            [{"text": "📄 Show my settings"}],
            [{"text": "⬅️ Back"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_sens(game: str) -> dict:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")
    return {
        "keyboard": [
            [{"text": "SENS: Low"}, {"text": "SENS: Mid"}, {"text": "SENS: High"}],
            [{"text": "⬅️ Назад" if ru else "⬅️ Back"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_fov(game: str) -> dict:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")
    return {
        "keyboard": [
            [{"text": "FOV: 100"}, {"text": "FOV: 110"}, {"text": "FOV: 120"}],
            [{"text": "⬅️ Назад" if ru else "⬅️ Back"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_aim(game: str) -> dict:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")
    return {
        "keyboard": [
            [{"text": "AIM: Default"}, {"text": "AIM: Strong"}, {"text": "AIM: Demon"}],
            [{"text": "⬅️ Назад" if ru else "⬅️ Back"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def presets(game: str) -> dict:
    g = (game or "warzone").lower()

    # ВАЖНО: это “пресеты” как стартовые, дальше ты расширишь под патчи/мету.
    # Warzone/BO7 (RU), BF6 labels are EN but values same.
    return {
        "pc": {
            "platform": "pc",
            "input_hint": "kbm",
            "fov": 120,
            "sens": "mid",
            "aim": "default",
            "audio": "high",
            "graphics": "competitive",
            "gameplay": "fast",
        },
        "ps": {
            "platform": "playstation",
            "input_hint": "controller",
            "fov": 110,
            "sens": "mid",
            "aim": "strong",
            "audio": "high",
            "graphics": "competitive",
            "gameplay": "stable",
        },
        "xbox": {
            "platform": "xbox",
            "input_hint": "controller",
            "fov": 110,
            "sens": "mid",
            "aim": "strong",
            "audio": "high",
            "graphics": "competitive",
            "gameplay": "stable",
        },
    }


def render_settings(game: str, s: dict) -> str:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")

    # BF6: settings titles in EN only
    if not ru:
        return (
            "📄 BF6 SETTINGS\n\n"
            f"Platform: {s.get('platform','—')}\n"
            f"Input hint: {s.get('input_hint','—')}\n"
            f"FOV: {s.get('fov','—')}\n"
            f"Sensitivity: {s.get('sens','—')}\n"
            f"Aim/Stick: {s.get('aim','—')}\n"
            f"Audio: {s.get('audio','—')}\n"
            f"Graphics: {s.get('graphics','—')}\n"
            f"Gameplay: {s.get('gameplay','—')}\n"
        )

    return (
        "📄 НАСТРОЙКИ ИГРЫ\n\n"
        f"Платформа: {s.get('platform','—')}\n"
        f"Input подсказка: {s.get('input_hint','—')}\n"
        f"FOV: {s.get('fov','—')}\n"
        f"Чувствительность: {s.get('sens','—')}\n"
        f"Аим/Стик: {s.get('aim','—')}\n"
        f"Аудио: {s.get('audio','—')}\n"
        f"Графика: {s.get('graphics','—')}\n"
        f"Геймплей: {s.get('gameplay','—')}\n"
    )
