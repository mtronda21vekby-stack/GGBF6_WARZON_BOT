# -*- coding: utf-8 -*-
"""
app/reply_kb.py

Нижние кнопки (ReplyKeyboard) — панель управления.
INLINE-кнопки (inline_keyboard) остаются в app/ui.py как “премиум-панель”.

Идея:
- Главная нижняя панель: быстрый вход в Warzone / BO7 / BF6 / Zombies + меню/профиль/настройки
- Внутри каждой игры — своя нижняя панель с разделами
"""

from typing import Dict, Any


def remove_reply_keyboard() -> Dict[str, Any]:
    return {"remove_keyboard": True}


def kb_root() -> Dict[str, Any]:
    """Главная нижняя панель (всегда доступна)."""
    return {
        "keyboard": [
            [{"text": "🎮 Warzone"}, {"text": "🎮 BO7"}, {"text": "🎮 BF6"}],
            [{"text": "🧟 Zombies"}, {"text": "⚙️ Настройки"}, {"text": "👤 Профиль"}],
            [{"text": "🏠 Меню"}],
        ],
        "resize_keyboard": True
    }


def kb_warzone() -> Dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "⚙️ Настройки WZ"}, {"text": "🔥 PRO-настройки WZ"}],
            [{"text": "🎯 Тренировка WZ"}, {"text": "🎬 VOD WZ"}],
            [{"text": "🖥 Устройство WZ"}, {"text": "👑 Уровень WZ"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }


def kb_bo7() -> Dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "⚙️ Настройки BO7"}, {"text": "🔥 PRO-настройки BO7"}],
            [{"text": "🎯 Тренировка BO7"}, {"text": "🎬 VOD BO7"}],
            [{"text": "🖥 Устройство BO7"}, {"text": "👑 Уровень BO7"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }


def kb_bf6() -> Dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "⚙️ Settings BF6"}, {"text": "🔥 PRO Settings BF6"}],
            [{"text": "🎯 Training BF6"}, {"text": "🎬 VOD BF6"}],
            [{"text": "🖥 Device BF6"}, {"text": "👑 Tier BF6"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }


def kb_device_pick_ru(prefix: str) -> Dict[str, Any]:
    """
    Универсальный выбор устройства.
    prefix: "wz" | "bo7" | "bf6"
    """
    return {
        "keyboard": [
            [{"text": f"🎮 PS5/Xbox ({prefix})"}, {"text": f"🖥 PC MnK ({prefix})"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }


def kb_tier_pick_ru(prefix: str) -> Dict[str, Any]:
    """
    Выбор уровня пресета: normal/demon/pro
    prefix: "wz" | "bo7" | "bf6"
    """
    return {
        "keyboard": [
            [{"text": f"🙂 Normal ({prefix})"}, {"text": f"😈 Demon ({prefix})"}],
            [{"text": f"🧠 Pro ({prefix})"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True
    }
