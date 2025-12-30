# app/ui/zombies_kb.py
# -*- coding: utf-8 -*-
from __future__ import annotations


# =========================================================
# ROUTER-COMPAT KEYBOARDS (ВАЖНО!)
# router.py импортирует:
#   kb_zombies_hub, kb_zombies_maps, kb_zombies_map_menu
# =========================================================

def kb_zombies_hub() -> dict:
    return {
        "keyboard": [
            [{"text": "🗺 Карты"}, {"text": "🧪 Перки"}],
            [{"text": "🔫 Оружие"}, {"text": "🥚 Пасхалки"}],
            [{"text": "🧠 Стратегия раундов"}, {"text": "⚡ Быстрые советы"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Zombies: карта | раунд | от чего падаешь | что открыл…",
    }


def kb_zombies_maps() -> dict:
    # router ожидает именно эти кнопки: "🧟 Ashes" / "🧟 Astra"
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
    m = (map_name or "Ashes").strip()

    # router ловит варианты:
    # "🧟 Ashes: Обзор", "🧟 Ashes: Перки", "🧟 Ashes: Оружие", "🧟 Ashes: Пасхалки",
    # "🧟 Ashes: Стратегия", "🧟 Ashes: Быстрые советы"
    return {
        "keyboard": [
            [{"text": f"🧟 {m}: Обзор"}, {"text": f"🧟 {m}: Перки"}],
            [{"text": f"🧟 {m}: Оружие"}, {"text": f"🧟 {m}: Пасхалки"}],
            [{"text": f"🧟 {m}: Стратегия"}, {"text": f"🧟 {m}: Быстрые советы"}],
            [{"text": "🗺 Карты"}, {"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": f"{m}: раунд | проблема | что открыл…",
    }
