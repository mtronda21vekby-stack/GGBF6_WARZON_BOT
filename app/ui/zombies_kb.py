# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_zombies_hub() -> dict:
    return {
        "keyboard": [
            [{"text": "🗺 Карты"}, {"text": "🧪 Перки"}, {"text": "🔫 Оружие"}],
            [{"text": "🥚 Пасхалки"}, {"text": "🧠 Стратегия раундов"}, {"text": "⚡ Быстрые советы"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Зомби: выбери пункт…",
    }


def kb_zombies_maps() -> dict:
    return {
        "keyboard": [
            [{"text": "🧟 Ashes"}, {"text": "🧟 Astra"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Выбери карту…",
    }


def kb_zombies_map_menu(map_name: str) -> dict:
    m = (map_name or "").strip()
    title = "🧟 " + (m if m else "Map")
    return {
        "keyboard": [
            [{"text": f"{title}: Обзор"}, {"text": f"{title}: Перки"}],
            [{"text": f"{title}: Оружие"}, {"text": f"{title}: Пасхалки"}],
            [{"text": f"{title}: Стратегия"}, {"text": f"{title}: Быстрые советы"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Что открыть по карте?",
    }
